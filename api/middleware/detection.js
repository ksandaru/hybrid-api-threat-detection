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
    // Fail open (NFR2): no features means no basis to judge, so let it through.
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

  // Consult the classifier only in hybrid mode, only when no high-severity rule
  // has fired (that verdict is final, so the call buys nothing and skipping it
  // is what keeps the cascade cheap), and only on payload-bearing endpoints.
  //
  // The last condition is load-bearing: the payload model has signal on a search
  // query and none on a credential body, and scored ~17% of ordinary logins as
  // attacks until it was scoped. See config.mlPayloadPaths.
  //
  // originalUrl, not req.path -- Express strips the '/api' mount prefix.
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

  // Allowed requests otherwise discard their score, which is exactly what
  // threshold recalibration needs. Set before the response is sent -- 'finish'
  // is too late for a header. Trace-gated so normal responses disclose nothing.
  if (process.env.DETECTION_TRACE === '1' && !res.headersSent) {
    res.set('X-Detection-Score', combined.score.toFixed(4));
    res.set('X-Detection-Rule-Score', rules.ruleScore.toFixed(4));
    if (mlScore != null) res.set('X-Detection-Ml-Score', mlScore.toFixed(4));
    res.set('X-Detection-Decision', decision);
  }

  res.on('finish', () => {
    // event.path, captured at entry: Express has since shortened req.path to
    // '/login'. Only allowed requests reached the auth handler, so a blocked one
    // stays unresolved -- scoring a 403 as a successful login would drag the
    // failure ratio down and unblock the next attempt.
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
