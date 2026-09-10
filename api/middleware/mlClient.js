const axios = require('axios');
const config = require('../config');

const TIMEOUT_MS = parseInt(process.env.ML_TIMEOUT_MS, 10) || 250;

// One shared client keeps the connection pool warm. A fresh agent per request
// would put a TCP handshake on a path that is already latency-constrained.
const client = axios.create({
  baseURL: config.mlServiceUrl,
  timeout: TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
});

let consecutiveFailures = 0;

// The service's decision boundary, read from /meta and used to put the ML score
// on the rule score's scale before combining (see scoreCombiner.js). Fetched
// lazily so a service restart with new weights is picked up without an API restart.
let mlBoundary = null;

async function boundary() {
  if (mlBoundary !== null) return mlBoundary;
  try {
    const res = await client.get('/meta');
    if (res.data && typeof res.data.attack_threshold === 'number') {
      mlBoundary = res.data.attack_threshold;
      console.log(`[mlClient] inference decision boundary = ${mlBoundary}`);
    }
  } catch (err) {
    // Not fatal: the combiner reads a null boundary as "do not rescale".
  }
  return mlBoundary;
}

// Score one feature vector. Resolves to
//   { ok: true,  score, isAttack, serviceLatencyMs, roundTripMs, details }
//   { ok: false, error, roundTripMs }
async function predict(features) {
  const started = process.hrtime.bigint();
  try {
    const res = await client.post('/predict', { features });
    const roundTripMs = Number(process.hrtime.bigint() - started) / 1e6;

    // The service reports failures in the body, so a 200 alone is not enough.
    if (!res.data || typeof res.data.score !== 'number' || res.data.error) {
      consecutiveFailures += 1;
      return {
        ok: false,
        error: (res.data && res.data.error) || 'malformed response',
        roundTripMs,
      };
    }

    if (consecutiveFailures > 0) {
      console.warn(`[mlClient] inference service recovered after ${consecutiveFailures} failure(s)`);
      consecutiveFailures = 0;
    }

    return {
      ok: true,
      score: res.data.score,
      isAttack: !!res.data.is_attack,
      serviceLatencyMs: res.data.latency_ms,
      roundTripMs,
      details: res.data.details,
    };
  } catch (err) {
    const roundTripMs = Number(process.hrtime.bigint() - started) / 1e6;
    consecutiveFailures += 1;
    // First failure, then every tenth: an outage stays visible without the log
    // filling up for its whole duration.
    if (consecutiveFailures === 1 || consecutiveFailures % 10 === 0) {
      const reason = err.code === 'ECONNABORTED'
        ? `timeout after ${TIMEOUT_MS}ms`
        : (err.code || err.message);
      console.warn(
        `[mlClient] inference unavailable (${reason}); falling back to rules. ` +
        `consecutive failures: ${consecutiveFailures}`
      );
    }
    return { ok: false, error: err.code || err.message, roundTripMs };
  }
}

function stats() {
  return { consecutiveFailures, timeoutMs: TIMEOUT_MS, baseURL: config.mlServiceUrl };
}

module.exports = { predict, stats, boundary, TIMEOUT_MS };
