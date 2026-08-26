const PAYLOAD_FEATURES = [
  'payload_length',
  'sql_keyword_count',
  'single_quote_count',
  'double_dash_count',
  'semicolon_count',
  'paren_count',
  'equals_count',
  'special_char_ratio',
  'shannon_entropy',
  'has_union_select',
  'has_or_equals',
  'has_comment',
];

const FLOW_FEATURES = [
  'requests_per_min_ip',
  'login_failure_ratio',
  'inter_arrival_time_variance',
  'distinct_usernames_tried',
  'unique_ip_count_window',
];

const CANONICAL_FEATURE_ORDER = [...PAYLOAD_FEATURES, ...FLOW_FEATURES];

const SQL_KEYWORDS = [
  'select', 'union', 'insert', 'update', 'delete', 'drop', 'create',
  'alter', 'exec', 'execute', 'declare', 'cast', 'convert', 'waitfor',
  'sleep', 'benchmark', 'information_schema', 'sysobjects', 'syscolumns',
  'xp_', 'sp_', 'or', 'and', 'having', 'group by', 'order by',
];

// Mirrors set("'\";()=--#*%<>{}[]|&+") in ml/features.py. The doubled
// hyphen collapses to a single set member, so it appears once here.
const SPECIAL_CHARS = new Set([
  "'", '"', ';', '(', ')', '=', '-', '#', '*', '%',
  '<', '>', '{', '}', '[', ']', '|', '&', '+',
]);

const KEYWORD_PATTERNS = SQL_KEYWORDS.map(
  (kw) => new RegExp('\\b' + kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'g')
);

const WINDOW_MS = 60 * 1000;

function shannonEntropy(text) {
  if (!text) return 0.0;
  const chars = Array.from(text);
  const counts = new Map();
  for (const ch of chars) counts.set(ch, (counts.get(ch) || 0) + 1);
  const length = chars.length;
  let total = 0;
  for (const count of counts.values()) {
    const p = count / length;
    total += p * Math.log2(p);
  }
  return -total;
}

function countOccurrences(haystack, needle) {
  return haystack.split(needle).length - 1;
}

function extractPayloadFeatures(text) {
  const s = text == null ? '' : String(text);
  const lower = s.toLowerCase();
  const chars = Array.from(s);
  const length = chars.length;

  let specialCharCount = 0;
  for (const ch of chars) if (SPECIAL_CHARS.has(ch)) specialCharCount += 1;

  let keywordCount = 0;
  for (const pattern of KEYWORD_PATTERNS) {
    pattern.lastIndex = 0;
    const found = lower.match(pattern);
    if (found) keywordCount += found.length;
  }

  return {
    payload_length: length,
    sql_keyword_count: keywordCount,
    single_quote_count: countOccurrences(s, "'"),
    double_dash_count: countOccurrences(s, '--'),
    semicolon_count: countOccurrences(s, ';'),
    paren_count: countOccurrences(s, '(') + countOccurrences(s, ')'),
    equals_count: countOccurrences(s, '='),
    special_char_ratio: length ? specialCharCount / length : 0.0,
    shannon_entropy: shannonEntropy(s),
    has_union_select: /union\s+select/.test(lower) ? 1 : 0,
    has_or_equals: /\bor\b[\s\S]{0,15}=/.test(lower) ? 1 : 0,
    has_comment: (s.includes('--') || s.includes('#') || s.includes('/*')) ? 1 : 0,
  };
}

function defaultFlowFeatures() {
  const out = {};
  for (const name of FLOW_FEATURES) out[name] = 0.0;
  return out;
}

function defaultPayloadFeatures() {
  const out = {};
  for (const name of PAYLOAD_FEATURES) out[name] = 0.0;
  return out;
}

/* ------------------------------------------------------------------ *
 * Per-source sliding window.
 *
 * Held in process memory. This is sufficient for the single-node
 * evaluation this project performs and is a documented limitation: the
 * window does not survive a restart and is not shared between instances,
 * so these features would need an external store before the framework
 * could be scaled horizontally.
 * ------------------------------------------------------------------ */

const ipEvents = new Map();       // ip   -> [{ ts, path, username, loginFailed }]
const endpointEvents = new Map(); // path -> [{ ip, ts }]

function prune(list, now) {
  const cutoff = now - WINDOW_MS;
  let i = 0;
  while (i < list.length && list[i].ts < cutoff) i += 1;
  if (i > 0) list.splice(0, i);
  return list;
}

/**
 * Drop map entries whose event lists have emptied.
 *
 * Pruning only happens for a source when that source is next seen, so a source
 * that sends a burst and never returns leaves an empty array behind forever.
 * One stale key is trivial; one per source address is a leak, and the Phase 8
 * attack simulation deliberately generates traffic from many distinct sources.
 *
 * Runs on a timer rather than on every request so the cost is not paid on the
 * request path. The handle is unref'd so it cannot hold the process open at
 * shutdown.
 */
function sweep(now = Date.now()) {
  let removed = 0;
  for (const [ip, events] of ipEvents) {
    if (prune(events, now).length === 0) {
      ipEvents.delete(ip);
      removed += 1;
    }
  }
  for (const [path, seen] of endpointEvents) {
    if (prune(seen, now).length === 0) endpointEvents.delete(path);
  }
  return removed;
}

const sweepTimer = setInterval(() => sweep(), WINDOW_MS);
if (typeof sweepTimer.unref === 'function') sweepTimer.unref();

function recordRequest(ip, path, username, now = Date.now()) {
  if (!ipEvents.has(ip)) ipEvents.set(ip, []);
  const events = prune(ipEvents.get(ip), now);
  const event = { ts: now, path, username: username || null, loginFailed: null };
  events.push(event);

  if (!endpointEvents.has(path)) endpointEvents.set(path, []);
  const seen = prune(endpointEvents.get(path), now);
  seen.push({ ip, ts: now });

  return event;
}

function computeFlowFeatures(ip, path, now = Date.now()) {
  const events = prune(ipEvents.get(ip) || [], now);
  const features = defaultFlowFeatures();

  features.requests_per_min_ip = events.length;

  const loginAttempts = events.filter((e) => e.path.includes('/auth/login'));
  const resolved = loginAttempts.filter((e) => e.loginFailed !== null);
  if (resolved.length > 0) {
    const failed = resolved.filter((e) => e.loginFailed).length;
    features.login_failure_ratio = failed / resolved.length;
  }

  // Population variance of inter-arrival gaps, in microseconds squared,
  // matching the units of the training corpus (see header note).
  if (events.length >= 3) {
    const gaps = [];
    for (let i = 1; i < events.length; i += 1) {
      gaps.push((events[i].ts - events[i - 1].ts) * 1000);
    }
    const mean = gaps.reduce((a, b) => a + b, 0) / gaps.length;
    features.inter_arrival_time_variance =
      gaps.reduce((acc, g) => acc + (g - mean) ** 2, 0) / gaps.length;
  }

  const usernames = new Set(events.map((e) => e.username).filter(Boolean));
  features.distinct_usernames_tried = usernames.size;

  const seen = prune(endpointEvents.get(path) || [], now);
  features.unique_ip_count_window = new Set(seen.map((e) => e.ip)).size;

  return features;
}

/* ------------------------------------------------------------------ *
 * Request -> inspected text
 * ------------------------------------------------------------------ */

function safeDecode(value) {
  try {
    return decodeURIComponent(value.replace(/\+/g, ' '));
  } catch (err) {
    return value; // malformed percent-encoding: inspect it exactly as sent
  }
}

/**
 * Builds the string the payload features are computed over.
 *
 * The shape mirrors how CSIC 2010 rows are assembled in ml/preprocess.py
 * (URI, then query string, then body) so that live requests are described
 * the same way the training rows were.
 */
function requestText(req) {
  const parts = [req.path || ''];

  const url = req.originalUrl || '';
  const qIndex = url.indexOf('?');
  if (qIndex !== -1) parts.push(safeDecode(url.slice(qIndex + 1)));

  if (req.body && typeof req.body === 'object') {
    const pairs = Object.entries(req.body).map(
      ([k, v]) => k + '=' + (typeof v === 'object' ? JSON.stringify(v) : String(v))
    );
    if (pairs.length) parts.push(pairs.join('&'));
  }

  return parts.filter(Boolean).join(' ');
}

function extractFeatures(req, now = Date.now()) {
  const ip = req.ip || (req.connection && req.connection.remoteAddress) || 'unknown';
  const path = req.path || '';
  const username =
    req.body && typeof req.body === 'object' ? req.body.username : null;

  const event = recordRequest(ip, path, username, now);
  const text = requestText(req);

  const features = {
    ...extractPayloadFeatures(text),
    ...computeFlowFeatures(ip, path, now),
  };

  return { features, event, ip, text };
}

function toVector(features) {
  return CANONICAL_FEATURE_ORDER.map((name) => features[name]);
}

function resetStore() {
  ipEvents.clear();
  endpointEvents.clear();
}

/**
 * Live sizes of the in-memory window, for the /health endpoint and for tests.
 *
 * Prunes as it counts, rather than reporting raw map contents. The background
 * sweep only runs once per window, so between sweeps a map still holds events
 * that have already aged out. A caller asking "is the window clear yet?" -- the
 * simulation harness waiting to start, the integration test's dirty-window
 * guard -- needs the answer as of now, not as of the last sweep, or it waits on
 * events that are already gone.
 */
function storeStats(now = Date.now()) {
  let events = 0;
  let sources = 0;
  for (const list of ipEvents.values()) {
    const live = prune(list, now).length;
    events += live;
    if (live > 0) sources += 1;
  }
  let endpoints = 0;
  for (const seen of endpointEvents.values()) {
    if (prune(seen, now).length > 0) endpoints += 1;
  }
  return { sources, endpoints, events };
}

function stopSweep() {
  clearInterval(sweepTimer);
}

module.exports = {
  PAYLOAD_FEATURES,
  FLOW_FEATURES,
  CANONICAL_FEATURE_ORDER,
  SQL_KEYWORDS,
  WINDOW_MS,
  shannonEntropy,
  extractPayloadFeatures,
  defaultFlowFeatures,
  defaultPayloadFeatures,
  recordRequest,
  computeFlowFeatures,
  requestText,
  extractFeatures,
  toVector,
  resetStore,
  sweep,
  storeStats,
  stopSweep,
};
