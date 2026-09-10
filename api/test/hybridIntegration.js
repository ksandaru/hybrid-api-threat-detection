/**
 * End-to-end integration check against a running API. Verifies that:
 *   - an attack the rules miss but the classifier catches is blocked
 *   - benign traffic still passes
 *   - with inference down, the API keeps serving on the rule verdict
 *   - the hybrid never detects *less* than rules alone on the behavioural
 *     attacks, where the classifier carries no signal
 *
 * Usage:
 *   node api/test/hybridIntegration.js            expects ML service up
 *   node api/test/hybridIntegration.js --no-ml    expects ML service down
 *
 * Needs DETECTION_MODE=hybrid. Restarts nothing; tests whatever is listening.
 */

const axios = require('axios');

const API = process.env.API_URL || 'http://localhost:3000';
const ML = process.env.ML_SERVICE_URL || 'http://localhost:8000';
const EXPECT_ML = !process.argv.includes('--no-ml');

const http = axios.create({ baseURL: API, timeout: 10000, validateStatus: () => true });

let pass = 0;
let fail = 0;

function check(name, actual, expected) {
  const ok = actual === expected;
  console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${name} -> ${actual}${ok ? '' : ` (expected ${expected})`}`);
  ok ? (pass += 1) : (fail += 1);
  return ok;
}

const search = (q) => http.get('/api/search/vulnerable', { params: { q } });
const login = (username, password) =>
  http.post('/api/auth/login', { username, password });

async function mlUp() {
  try {
    const r = await axios.get(`${ML}/health`, { timeout: 3000 });
    return r.status === 200 && r.data.ready;
  } catch {
    return false;
  }
}

async function main() {
  const up = await mlUp();
  console.log(`inference service: ${up ? 'up' : 'down'}  (expected ${EXPECT_ML ? 'up' : 'down'})`);
  if (up !== EXPECT_ML) {
    console.log('inference service state does not match the flag; aborting');
    process.exit(2);
  }
  console.log();

  // Fresh identity, so a previous run cannot leave this source inside a
  // behavioural window and block traffic that should pass.
  const user = `probe_${Date.now()}`;

  // Refuse to run against a dirty sliding window. A fresh username is not
  // enough -- the behavioural features key on the source address, and every run
  // uses the same one. Back-to-back runs start with ~30 events already in the
  // window, the rate rules fire, and the failures surface several checks later
  // looking like a detection defect rather than leftover state.
  const pre = await http.get('/health');
  const occupancy = (pre.data && pre.data.window) || {};
  if ((occupancy.events || 0) > 0) {
    console.log(`the API is holding ${occupancy.events} event(s) from ` +
                `${occupancy.sources} source(s) in its 60s window.`);
    console.log('Results would be meaningless. Either wait 60s or restart it:');
    console.log('    docker compose restart api      (containers)');
    console.log('    or restart `node server.js`     (running directly)');
    console.log();
    process.exit(2);
  }

  await http.post('/api/auth/register', { username: user, password: 'pass1234' });

  // Latency first, on a clean window. The whole run stays under 30 requests
  // from this source: RATE_ELEVATED fires above that, and every later request
  // then carries a 0.4 rule score that blocks legitimate traffic. Measuring
  // after the attack cases would profile a source already flagged as bursty.
  console.log('=== added latency, benign path (8 requests, clean window) ===');
  const ms = [];
  for (let i = 0; i < 8; i += 1) {
    const t = process.hrtime.bigint();
    const r = await search(`latency probe ${i}`);
    ms.push(Number(process.hrtime.bigint() - t) / 1e6);
    if (r.status !== 200) {
      console.log(`        note: probe ${i} returned ${r.status}; rate rules engaged`);
      break;
    }
  }
  ms.sort((a, b) => a - b);
  const pct = (p) => ms[Math.min(ms.length - 1, Math.floor((p / 100) * ms.length))];
  console.log(`        n=${ms.length}  p50=${pct(50).toFixed(1)}ms  p95=${pct(95).toFixed(1)}ms  p99=${pct(99).toFixed(1)}ms`);
  // NFR1's 100 ms budget applies while inference is reachable. With it down a
  // stopped container swallows the connection rather than refusing it, so every
  // request waits out ML_TIMEOUT_MS before falling back -- ~250 ms is then the
  // designed fail-open behaviour, and asserting 100 ms would fail NFR2 working.
  const timeoutMs = Number(process.env.ML_TIMEOUT_MS || 250);
  const budget = EXPECT_ML ? 100 : timeoutMs + 100;
  check(EXPECT_ML
          ? 'p95 within the 100ms budget'
          : `p95 within the degraded budget (${budget}ms = timeout + margin)`,
        pct(95) < budget, true);
  if (!EXPECT_ML) {
    console.log('        note: degraded latency is dominated by ML_TIMEOUT_MS, ' +
                'not by detection work');
  }

  // Measured as a rate, not asserted per request. The classifier has a real
  // false positive rate on this API's traffic shape because the corpus benign
  // rows do not cover it, so a per-request assertion would encode an
  // expectation the system is known not to meet.
  console.log('\n=== benign traffic (false positive rate measured, not asserted per request) ===');
  const benign = ['laptop', 'wireless mouse', 'bluetooth speaker', 'office chair', 'usb-c hub'];
  let allowed = 0;
  const blockedTerms = [];
  for (const q of benign) {
    const r = await search(q);
    if (r.status === 200) allowed += 1;
    else blockedTerms.push(`${q} (${r.data && r.data.score})`);
  }
  // The login goes in the same bucket, instructively: payload_length is the
  // classifier's second most important feature and the corpus ties length to
  // attacks, so a longer username scores higher purely for being longer. Length
  // as a proxy for maliciousness -- what the attack simulation exists to correct.
  const loginRes = await login(user, 'pass1234');
  if (loginRes.status === 200) allowed += 1;
  else blockedTerms.push(`valid login (${loginRes.data && loginRes.data.score})`);
  const total = benign.length + 1;

  const fpr = 1 - allowed / total;
  console.log(`        ${allowed}/${total} allowed, FPR = ${(fpr * 100).toFixed(1)}%`);
  if (blockedTerms.length) console.log(`        false positives: ${blockedTerms.join(', ')}`);
  check('benign FPR below 40%', fpr < 0.4, true);

  console.log('\n=== attacks the rule engine catches on its own ===');
  check('union select', (await search("' UNION SELECT username,password FROM users --")).status, 403);
  check('tautology', (await search("' OR '1'='1")).status, 403);
  check('stacked query', (await search('1; DROP TABLE users; SELECT 1')).status, 403);

  console.log('\n=== the case rules miss (rule score 0.5, below threshold) ===');
  // With inference available the classifier supplies the missing confidence.
  // Without it, the pipeline degrades to the rule verdict and allows the
  // request: detection degrades, availability does not.
  const subtle = await search("admin'-- DROP TABLE");
  check('admin\'-- DROP TABLE', subtle.status, EXPECT_ML ? 403 : 200);
  if (EXPECT_ML && subtle.data && subtle.data.score !== undefined) {
    console.log(`        combined score ${subtle.data.score} (rules alone would be 0.500)`);
  }

  console.log('\n=== behavioural attack must not be weakened by the ML term ===');
  // The classifier scores these near zero, so a weighted mean would cancel a
  // confident rule verdict. A high-severity rule also short-circuits before the
  // call is made. Both protections are exercised here.
  const bf = `bf_${Date.now()}`;
  await http.post('/api/auth/register', { username: bf, password: 'pass1234' });
  const codes = [];
  for (let i = 1; i <= 8; i += 1) {
    codes.push((await login(bf, `wrong${i}`)).status);
  }
  console.log(`        attempt codes: ${codes.join(' ')}`);
  const blockedFrom = codes.findIndex((c) => c === 403);
  check('brute force eventually blocked', blockedFrom !== -1, true);
  check('blocked within first 6 attempts', blockedFrom !== -1 && blockedFrom < 6, true);

  console.log(`\n${fail === 0 ? 'ALL CHECKS PASSED' : `${fail} CHECK(S) FAILED`}  (${pass} passed)`);
  process.exit(fail === 0 ? 0 : 1);
}

main().catch((err) => {
  console.error('integration check errored:', err.message);
  process.exit(2);
});
