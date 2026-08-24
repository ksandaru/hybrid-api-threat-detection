/**
 * Detection orchestrator.
 *
 * Sits in the Express pipeline ahead of every /api route, so coverage is
 * structural: a newly added endpoint is inspected by default rather than by
 * remembering to protect it.
 *
 * Per request:
 *   1. extract the shared feature vector, updating the sliding window first so
 *      the current request is included in the statistics used to judge it
 *   2. evaluate the rule filter
 *   3. if a high-severity rule fired, reject immediately without consulting the
 *      classifier -- the cheap deterministic path handles what it can handle,
 *      and the expensive adaptive path is reserved for what needs it
 *   4. otherwise, in hybrid mode, score the same feature vector at the
 *      inference service and combine the two results
 *   5. reject if the combined score reaches the threshold
 *   6. record the outcome, off the critical path
 *
 * DETECTION_MODE selects behaviour, which is how the Phase 9 evaluation builds
 * its baseline configurations without changing code:
 *   off    - observe and log only, never block  (measures the no-control case)
 *   rules  - rule filter only                   (baseline 1)
 *   hybrid - rules plus ML                      (the proposed framework)
 *
 * Fail-open (NFR2): if inference is unreachable, slow or malformed, the request
 * is judged on the rule verdict alone and a warning is logged. Detection
 * degrades; availability does not. See scoreCombiner.js for why the combination
 * is a noisy-OR rather than the weighted mean the specification suggests.
 */

const config = require('../config');
const { extractFeatures } = require('./featureExtractor');
const ruleEngine = require('./ruleEngine');
const mlClient = require('./mlClient');
const { combine } = require('./scoreCombiner');
const { logRequest } = require('../db/pool');

const COMBINE_STRATEGY = process.env.COMBINE_STRATEGY || undefined;
const W_RULE = process.env.W_RULE ? parseFloat(process.env.W_RULE) : undefined;
const W_ML = process.env.W_ML ? parseFloat(process.env.W_ML) : undefined;

async function detectionMiddleware(req, res, next) {
  const startedAt = process.hrtime.bigint();

  let extraction;
  try {
    extraction = extractFeatures(req);
  } catch (err) {
    // Feature extraction must never take the API down. If it fails there is no
    // basis on which to judge the request, so it is allowed and the failure is
    // reported rather than silently swallowed.
    console.error('[detection] feature extraction failed, allowing request:', err.message);
    return next();
  }

  const { features, event, ip } = extraction;
  const mode = config.detectionMode;

  const rules = mode === 'off'
    ? { blocked: false, alerts: [], ruleScore: 0 }
    : ruleEngine.evaluate(features);

  let mlScore = null;
  let ml = null;
  let mlBoundary = null;

  // The classifier is consulted only when three things hold:
  //   - we are in hybrid mode
  //   - no high-severity rule has already fired (its verdict is certain, and
  //     the classifier cannot overturn it, so the call would buy nothing -- the
  //     short-circuit is what keeps the cascade cheap)
  //   - the request targets a payload-bearing endpoint
  //
  // The last condition is why benign logins are no longer blocked. The payload
  // model has signal on a search query and none on a credential body; applied
  // to auth it produced a ~17% false positive rate on ordinary logins while
  // adding nothing, because brute force and credential stuffing are caught
  // behaviourally by the rule stage. See config.mlPayloadPaths.
  // originalUrl, not req.path: this middleware is mounted at '/api', so by the
  // time it runs Express has already stripped that prefix from req.path
  // (req.path is '/search/vulnerable', not '/api/search/vulnerable').
  // originalUrl keeps the full path, so the configured prefixes read naturally.
  const targetPath = req.originalUrl || req.path || '';
  const payloadBearing = config.mlPayloadPaths.some((prefix) =>
    targetPath.startsWith(prefix));
  const needsMl = mode === 'hybrid' && !rules.blocked && payloadBearing;
  if (needsMl) {
    ml = await mlClient.predict(features);
    if (ml.ok) {
      mlScore = ml.score;
      mlBoundary = await mlClient.boundary();
    }
  }

  const combined = combine(rules.ruleScore, mlScore, {
    strategy: COMBINE_STRATEGY,
    wRule: W_RULE,
    wMl: W_ML,
    mlBoundary,
  });

  const shouldBlock =
    mode !== 'off' &&
    (rules.blocked || combined.score >= config.detectionThreshold);
  const decision = shouldBlock ? 'blocked' : 'allowed';

  req.detection = {
    features,
    rules,
    ml,
    combinedScore: combined.score,
    strategy: combined.strategy,
    decision,
  };

  // Under trace, attach the scores to every inspected response, allowed ones
  // included. A 403 already carries its score in the body, but an allowed
  // request discards it, and that is precisely the number threshold
  // recalibration needs: what combined score did benign traffic receive. Set
  // here, before the response is sent, because res.on('finish') is too late to
  // add a header. Trace-gated, so normal responses do not disclose the score.
  if (process.env.DETECTION_TRACE === '1' && !res.headersSent) {
    res.set('X-Detection-Score', combined.score.toFixed(4));
    res.set('X-Detection-Rule-Score', rules.ruleScore.toFixed(4));
    if (mlScore != null) res.set('X-Detection-Ml-Score', mlScore.toFixed(4));
    res.set('X-Detection-Decision', decision);
  }

  res.on('finish', () => {
    // Use the path captured at entry, not req.path. Express rewrites req.url as
    // it dispatches into nested routers, so by the time this fires req.path has
    // been shortened to '/login' and would never match here.
    //
    // Only requests that actually reached the auth handler carry a usable
    // outcome. A blocked request never got there, so it stays unresolved and is
    // excluded from the ratio -- otherwise a 403 would be recorded as a
    // successful login, pulling the failure ratio down and un-blocking the next
    // attempt in an oscillating loop.
    if (event && decision === 'allowed' && event.path.includes('/auth/login')) {
      event.loginFailed = res.statusCode === 401;
    }
    const elapsedMs = Number(process.hrtime.bigint() - startedAt) / 1e6;
    logRequest({
      method: req.method,
      path: req.originalUrl || req.path,
      ip,
      features,
      decision,
    });
    if (process.env.DETECTION_TRACE === '1') {
      const mlPart = ml
        ? (ml.ok
            ? `ml=${ml.score.toFixed(3)}~${(combined.mlAligned == null ? ml.score : combined.mlAligned).toFixed(3)}(${ml.roundTripMs.toFixed(1)}ms)`
            : `ml=FAILED(${ml.error})`)
        : 'ml=skipped';
      console.log(
        `[detection] ${req.method} ${req.originalUrl} ip=${ip} ` +
        `rule=${rules.ruleScore.toFixed(3)} ${mlPart} ` +
        `combined=${combined.score.toFixed(3)} via=${combined.strategy} ` +
        `decision=${decision} rules=[${rules.alerts.map((a) => a.id).join(',')}] ` +
        `${elapsedMs.toFixed(2)}ms`
      );
    }
  });

  if (shouldBlock) {
    return res.status(403).json({
      error: 'request blocked by threat detection',
      score: Number(combined.score.toFixed(3)),
      alerts: rules.alerts.map((a) => ({ id: a.id, severity: a.severity, message: a.message })),
    });
  }

  return next();
}

module.exports = detectionMiddleware;
