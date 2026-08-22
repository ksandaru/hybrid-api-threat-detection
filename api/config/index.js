require('dotenv').config();

module.exports = {
  port: parseInt(process.env.PORT, 10) || 3000,
  mlServiceUrl: process.env.ML_SERVICE_URL || 'http://localhost:8000',
  databaseUrl: process.env.DATABASE_URL,
  detectionThreshold: parseFloat(process.env.DETECTION_THRESHOLD) || 0.7,
  // off | rules | hybrid  (see api/middleware/detection.js)
  detectionMode: process.env.DETECTION_MODE || 'rules',
  jwtSecret: process.env.JWT_SECRET || 'change-me-in-local-env',

  // Whether to believe X-Forwarded-For when deciding a request's source.
  //
  // Off by default, and that default is load-bearing. Every behavioural
  // feature this system has -- request rate, login failure ratio, distinct
  // usernames tried -- is keyed on source identity. Trusting a client-supplied
  // header means an attacker can rotate that identity per request and never
  // accumulate a window, defeating brute-force and credential-stuffing
  // detection entirely by adding one header.
  //
  // It exists because the Phase 8 harness runs many simulated clients from one
  // machine, and without distinct identities they share a source, trip the rate
  // rules collectively, and the harness ends up measuring its own load rather
  // than the attack it is simulating. In a real deployment this would only be
  // enabled behind a proxy that overwrites the header.
  trustProxy: process.env.TRUST_PROXY === '1',

  // Path prefixes where the ML payload classifier is consulted. Everywhere
  // else the verdict comes from the rule stage alone.
  //
  // The classifier's features -- SQL keyword count, UNION SELECT, quote and
  // comment counts -- describe a free-text query payload. They are meaningful
  // for a search endpoint and meaningless for a credential POST body, whose
  // high entropy and special-character density the model reads as an attack.
  // The Phase 8 traffic showed this directly: 21 of 25 benign auth requests
  // scored above 0.80, against 1 of 64 searches. The behavioural attacks that
  // do target auth -- brute force, credential stuffing -- are caught by the
  // rate and failure-ratio rules, which need no payload model. So the model is
  // applied where it has signal and withheld where it only has noise.
  // See evaluation/threshold_recalibration.md.
  mlPayloadPaths: (process.env.ML_PAYLOAD_PATHS || '/api/search')
    .split(',').map((p) => p.trim()).filter(Boolean),
};
