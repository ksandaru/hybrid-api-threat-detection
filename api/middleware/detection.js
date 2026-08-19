/**
 * Detection orchestrator.
 *
 * Sits in the Express pipeline ahead of every /api route, so coverage is
 * structural: a newly added endpoint is inspected by default rather than by
 * remembering to protect it.
 *
 * Current stage (rule-only). Per request:
 *   1. extract the shared feature vector, updating the sliding window first
 *      so the current request is included in the statistics used to judge it
 *   2. evaluate the rule filter
 *   3. reject with 403 if a high-severity rule fired, otherwise continue
 *   4. record the outcome, off the critical path
 *
 * The ML call and weighted score combination are added in Phase 6. The
 * insertion point is marked below.
 *
 * DETECTION_MODE selects behaviour, which is how the Phase 9 evaluation
 * builds its baseline configurations without changing code:
 *   off    - observe and log only, never block  (measures the no-control case)
 *   rules  - rule filter only                   (baseline 1)
 *   hybrid - rules plus ML                      (proposed framework, Phase 6)
 */

const config = require('../config');
const { extractFeatures } = require('./featureExtractor');
const ruleEngine = require('./ruleEngine');
const { logRequest } = require('../db/pool');

function detectionMiddleware(req, res, next) {
  const startedAt = process.hrtime.bigint();

  let extraction;
  try {
    extraction = extractFeatures(req);
  } catch (err) {
    // Feature extraction must never take the API down. If it fails we have
    // no basis on which to judge the request, so we allow it and say so.
    console.error('[detection] feature extraction failed, allowing request:', err.message);
    return next();
  }

  const { features, event, ip } = extraction;
  const rules = config.detectionMode === 'off'
    ? { blocked: false, alerts: [], ruleScore: 0 }
    : ruleEngine.evaluate(features);

  // TODO (Phase 6): when detectionMode === 'hybrid', call mlClient here,
  // combine ruleScore with mlScore, and compare against
  // config.detectionThreshold. Fail open to the rule verdict on timeout.
  // A high-severity rule rejects outright; otherwise accumulated medium
  // signal must clear the configured threshold. Phase 6 adds the ML score
  // to combinedScore before this same comparison.
  const combinedScore = rules.ruleScore;
  const shouldBlock =
    config.detectionMode !== 'off' &&
    (rules.blocked || combinedScore >= config.detectionThreshold);
  const decision = shouldBlock ? 'blocked' : 'allowed';

  req.detection = { features, rules, combinedScore, decision };

  // Authentication outcome feeds login_failure_ratio for subsequent
  // requests from this source, so it is captured once the status is known.
  res.on('finish', () => {
    // Use the path captured at entry, not req.path. Express rewrites req.url
    // as it dispatches into nested routers, so by the time this fires req.path
    // has been shortened to '/login' and would never match here.
    // Only requests that actually reached the auth handler carry a usable
    // outcome. A blocked request never got there, so it stays unresolved and
    // is excluded from the ratio -- otherwise a 403 would be recorded as a
    // successful login, pulling the failure ratio down and un-blocking the
    // next attempt in an oscillating loop.
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
      console.log(
        `[detection] ${req.method} ${req.originalUrl} ip=${ip} score=${combinedScore.toFixed(2)} ` +
        `decision=${decision} rules=[${rules.alerts.map((a) => a.id).join(',')}] ${elapsedMs.toFixed(2)}ms`
      );
    }
  });

  if (shouldBlock) {
    return res.status(403).json({
      error: 'request blocked by threat detection',
      score: Number(combinedScore.toFixed(3)),
      alerts: rules.alerts.map((a) => ({ id: a.id, severity: a.severity, message: a.message })),
    });
  }

  return next();
}

module.exports = detectionMiddleware;
