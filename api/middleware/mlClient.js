/**
 * Client for the Python inference service.
 *
 * The contract is deliberately narrow: send the 17-name feature object, receive
 * a score. This module knows nothing about which models exist or how their
 * outputs are combined, and the service knows nothing about HTTP requests.
 *
 * Every failure path returns `{ ok: false }` rather than throwing. The caller
 * treats that as a reason to fall back to the rule verdict, implementing the
 * fail-open policy in NFR2: a detection layer that is unreachable must not take
 * the API down with it. An availability incident caused by a security control
 * is still an availability incident.
 */

const axios = require('axios');
const config = require('../config');

const TIMEOUT_MS = parseInt(process.env.ML_TIMEOUT_MS, 10) || 250;

// Reusing one client keeps the connection pool warm; a fresh agent per request
// would add a TCP handshake to a path that is already latency-constrained.
const client = axios.create({
  baseURL: config.mlServiceUrl,
  timeout: TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
});

let consecutiveFailures = 0;

// The service's own decision boundary, discovered from /meta. The middleware
// needs it to put the ML score on the same scale as the rule score before
// combining -- see scoreCombiner.js. Discovered lazily and cached, so a service
// restart with different weights is picked up without restarting the API.
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
    // Not fatal. Without it the raw score is used, which is the pre-alignment
    // behaviour; the combiner treats a null boundary as "do not rescale".
  }
  return mlBoundary;
}

/**
 * Score one feature vector.
 *
 * Resolves to:
 *   { ok: true,  score, isAttack, serviceLatencyMs, roundTripMs, details }
 *   { ok: false, error, roundTripMs }
 */
async function predict(features) {
  const started = process.hrtime.bigint();
  try {
    const res = await client.post('/predict', { features });
    const roundTripMs = Number(process.hrtime.bigint() - started) / 1e6;

    // The service reports its own failures in the body rather than as a status
    // code, so a 200 is not on its own sufficient.
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
    // Log the first failure and then every tenth, so an outage is visible
    // without flooding the log on every request for its duration.
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
