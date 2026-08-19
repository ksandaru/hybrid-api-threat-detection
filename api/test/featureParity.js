/**
 * Feature contract parity test.
 *
 * Proves that api/middleware/featureExtractor.js and ml/features.py compute
 * identical payload feature vectors for identical input. This is the check
 * that enforces NFR3: if the two halves of the contract ever diverge, the
 * models receive inputs that do not mean what they were trained to mean,
 * and they will keep returning confident predictions that happen to be wrong.
 *
 * Run:  node api/test/featureParity.js
 * Exits non-zero on any mismatch, so it can gate a commit.
 */

const { execFileSync } = require('child_process');
const path = require('path');
const { extractPayloadFeatures, PAYLOAD_FEATURES } = require('../middleware/featureExtractor');

const ROOT = path.resolve(__dirname, '..', '..');
const PYTHON = path.join(ROOT, 'ml', 'venv', 'Scripts', 'python.exe');

// Cases chosen to exercise the places a naive port diverges: empty input,
// overlapping separators, comment syntax, word-boundary keyword matching,
// multi-byte characters, and percent-encoded payloads.
const CASES = [
  '',
  'laptop',
  'mouse keyboard monitor',
  "' OR '1'='1",
  "' OR '1'='1' UNION SELECT username, password FROM users --",
  "admin'--",
  '1; DROP TABLE users;',
  '/**/or/**/1/**/=/**/1',
  'SELECT * FROM t GROUP BY x ORDER BY y HAVING z = 1',
  'xp_cmdshell sp_executesql',
  'a---b',
  '((()))',
  '%27%20OR%201=1',
  'cafe ☕ select union',
  '\u{1F600}\u{1F600} drop table',
  'UNION    SELECT',
  'orange = 5',
  'or x=1',
  '/api/search/vulnerable q=laptop',
  "/api/auth/login username=admin&password=' OR 1=1 --",
];

function pythonFeatures(cases) {
  const script = [
    'import json, sys',
    'sys.path.insert(0, r"' + path.join(ROOT, 'ml') + '")',
    'from features import extract_payload_features',
    'cases = json.loads(sys.stdin.buffer.read().decode("utf-8"))',
    'print(json.dumps([extract_payload_features(c) for c in cases]))',
  ].join('\n');

  const out = execFileSync(PYTHON, ['-c', script], {
    input: JSON.stringify(cases),
    encoding: 'utf8',
  });
  return JSON.parse(out);
}

function close(a, b) {
  if (typeof a === 'number' && typeof b === 'number') {
    return Math.abs(a - b) <= 1e-12 * Math.max(1, Math.abs(a), Math.abs(b));
  }
  return a === b;
}

function main() {
  const py = pythonFeatures(CASES);
  let failures = 0;

  CASES.forEach((text, i) => {
    const js = extractPayloadFeatures(text);
    const ref = py[i];
    const bad = [];

    for (const name of PAYLOAD_FEATURES) {
      if (!close(js[name], ref[name])) {
        bad.push(`${name}: js=${js[name]} py=${ref[name]}`);
      }
    }

    if (bad.length) {
      failures += 1;
      console.log(`FAIL  ${JSON.stringify(text)}`);
      bad.forEach((b) => console.log(`        ${b}`));
    }
  });

  const checked = CASES.length * PAYLOAD_FEATURES.length;
  if (failures === 0) {
    console.log(`PASS  ${CASES.length} payloads x ${PAYLOAD_FEATURES.length} features = ${checked} comparisons, no divergence`);
    process.exit(0);
  }
  console.log(`\n${failures} of ${CASES.length} payloads diverged`);
  process.exit(1);
}

main();
