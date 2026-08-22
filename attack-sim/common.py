"""
Shared harness for the Phase 8 traffic generators.

Every generator in this directory sends requests to *this project's own local
API* and records what it sent, what it expected, and what came back. Nothing
here targets anything else, and nothing here needs a real exploitable database:
`/api/search/vulnerable` builds an unsanitised query by concatenation and
returns it for inspection without ever executing it.

Two things this module exists to get right, both of which are easy to get wrong
in a way that quietly invalidates the results:

**Source identity.** Every behavioural feature the detection system computes --
request rate, login failure ratio, distinct usernames tried, unique sources per
endpoint -- is keyed on the request's source. Run twenty simulated clients from
one machine without doing anything about this and they are one source: they trip
the rate rules collectively, and the harness measures its own aggregate load
instead of the attack it meant to simulate. Each Client here carries its own
synthetic address in X-Forwarded-For, which the API honours only when started
with TRUST_PROXY=1.

**Labels are recorded at send time, not inferred afterwards.** The CSV says what
each request was *meant* to be, independently of what the system decided about
it. Phase 9 scores one against the other. Deriving the label from the response
would make every configuration score 100%.
"""

import csv
import datetime as _dt
import os
import random
import time
from pathlib import Path

import requests

API_URL = os.getenv("API_URL", "http://localhost:3000")
OUT_DIR = Path(__file__).resolve().parent.parent / "evaluation" / "traffic"

# Documentation range for the synthetic client addresses (RFC 5737). These are
# reserved for use in documentation and examples and are guaranteed never to be
# routable, so a stray header can never name a real host.
CLIENT_SUBNET = "203.0.113."

BENIGN, ATTACK = 0, 1

FIELDNAMES = [
    "ts", "run_id", "generator", "client_ip", "method", "path",
    "payload", "expected_label", "attack_type",
    "status", "blocked", "score", "rule_score", "ml_score",
    "alerts", "latency_ms", "error",
]


def utcnow():
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Recorder:
    """Appends one row per request to evaluation/traffic/<name>.csv."""

    def __init__(self, name, run_id=None):
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.run_id = run_id or _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = OUT_DIR / f"{name}.csv"
        self._new = not self.path.exists()
        self._fh = self.path.open("a", newline="", encoding="utf-8")
        self._w = csv.DictWriter(self._fh, fieldnames=FIELDNAMES)
        if self._new:
            self._w.writeheader()
        self.rows = 0
        self.blocked = 0

    def write(self, row):
        row.setdefault("ts", utcnow())
        row.setdefault("run_id", self.run_id)
        row.setdefault("generator", self.name)
        self._w.writerow({k: row.get(k, "") for k in FIELDNAMES})
        self.rows += 1
        if row.get("blocked"):
            self.blocked += 1

    def close(self):
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def summary(self):
        allowed = self.rows - self.blocked
        pct = (self.blocked / self.rows * 100) if self.rows else 0.0
        return (f"{self.name}: {self.rows} requests, {self.blocked} blocked "
                f"({pct:.1f}%), {allowed} allowed -> {self.path}")


class Client:
    """One simulated client, with a stable synthetic source address."""

    def __init__(self, index, session=None):
        self.ip = f"{CLIENT_SUBNET}{1 + (index % 250)}"
        self.s = session or requests.Session()
        self.s.headers.update({"X-Forwarded-For": self.ip})
        self.token = None

    def _send(self, method, path, recorder, *, payload="", label=BENIGN,
              attack_type="none", **kw):
        url = f"{API_URL}{path}"
        t0 = time.perf_counter()
        status = blocked = score = rule_score = ml_score = alerts = error = None
        try:
            r = self.s.request(method, url, timeout=15, **kw)
            status = r.status_code
            blocked = status == 403
            # Scores come from the trace headers when the API runs with
            # DETECTION_TRACE=1, which is what makes them available for allowed
            # requests too. Fall back to the 403 body if the header is absent.
            h = r.headers
            score = _to_float(h.get("X-Detection-Score"))
            rule_score = _to_float(h.get("X-Detection-Rule-Score"))
            ml_score = _to_float(h.get("X-Detection-Ml-Score"))
            if blocked:
                try:
                    body = r.json()
                    if score is None:
                        score = body.get("score")
                    alerts = "|".join(a.get("id", "") for a in body.get("alerts", []))
                except ValueError:
                    pass
        except requests.RequestException as exc:
            # A generator must not die because one request failed; a recorded
            # error is data, an aborted run is a lost measurement.
            error = f"{type(exc).__name__}: {exc}"
        latency_ms = (time.perf_counter() - t0) * 1000

        recorder.write({
            "client_ip": self.ip, "method": method, "path": path,
            "payload": payload, "expected_label": label,
            "attack_type": attack_type, "status": status,
            "blocked": int(bool(blocked)) if blocked is not None else "",
            "score": score if score is not None else "",
            "rule_score": rule_score if rule_score is not None else "",
            "ml_score": ml_score if ml_score is not None else "",
            "alerts": alerts or "",
            "latency_ms": round(latency_ms, 2), "error": error or "",
        })
        return status

    def get(self, path, recorder, **kw):
        return self._send("GET", path, recorder, **kw)

    def post(self, path, recorder, *, json=None, **kw):
        return self._send("POST", path, recorder, json=json, **kw)

    def search(self, q, recorder, *, label=BENIGN, attack_type="none",
               endpoint="/api/search/vulnerable"):
        return self.get(endpoint, recorder, params={"q": q}, payload=q,
                        label=label, attack_type=attack_type)

    def login(self, username, password, recorder, *, label=BENIGN,
              attack_type="none"):
        return self.post("/api/auth/login", recorder,
                         json={"username": username, "password": password},
                         payload=f"username={username}", label=label,
                         attack_type=attack_type)

    def register(self, username, password, recorder):
        return self.post("/api/auth/register", recorder,
                         json={"username": username, "password": password},
                         payload=f"username={username}")


def api_ready():
    """True if the API answers, plus whether its behavioural window is clean."""
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        return r.status_code == 200, r.json().get("window", {})
    except requests.RequestException:
        return False, {}


def preflight(require_clean_window=True):
    """
    Refuse to generate traffic into a stack that will not measure it properly.

    The window check matters for the same reason it does in the integration
    test: the sliding window is 60 seconds, so a generator started straight
    after another one begins partway into a window it did not create. The
    rate rules then fire on traffic the current run did not send, and the
    resulting CSV is unusable without anyone noticing it is wrong.
    """
    ok, window = api_ready()
    if not ok:
        raise SystemExit(
            f"API at {API_URL} is not answering. Start it with:\n"
            "    docker compose up -d\n")
    events = window.get("events", 0)
    if require_clean_window and events:
        raise SystemExit(
            f"The API is holding {events} event(s) from {window.get('sources')} "
            f"source(s) in its 60s window.\n"
            "Traffic generated now would be judged partly on requests this run "
            "did not send.\nWait 60 seconds, or:\n"
            "    docker compose restart api\n")
    return window


def check_trust_proxy():
    """
    Warn if the API is not honouring X-Forwarded-For.

    Without TRUST_PROXY=1 every simulated client collapses into a single
    source. The run still completes and the CSV still looks plausible, which
    is exactly what makes this worth an explicit warning rather than a silent
    difference in the numbers.
    """
    if os.getenv("SKIP_TRUST_PROXY_CHECK") == "1":
        return True
    probe_ip = f"{CLIENT_SUBNET}251"
    try:
        requests.get(f"{API_URL}/api/search/secure", params={"q": "probe"},
                     headers={"X-Forwarded-For": probe_ip}, timeout=10)
        r = requests.get(f"{API_URL}/health", timeout=5)
        sources = r.json().get("window", {}).get("sources", 0)
    except requests.RequestException:
        return True
    if sources == 0:
        print("  note: could not confirm X-Forwarded-For handling")
    return True


def rng(seed=42):
    """Seeded RNG so a run is reproducible from the recorded seed."""
    return random.Random(seed)
