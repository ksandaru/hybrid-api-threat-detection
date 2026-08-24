"""
Benign traffic generator.

This is the most consequential script in Phase 8, and not because generating
normal traffic is difficult. Phase 6 measured a hybrid false positive rate of
33% against rules-only 0% on live-shaped benign traffic, and recorded it as a
deployment blocker. The cause is that the ML decision threshold (0.77) was
selected on corpus validation rows, which do not resemble what this API
actually receives. Recalibrating needs a body of representative benign traffic
to calibrate against. This produces it.

"Representative" is doing real work in that sentence. If this generator only
sends `laptop` and `mouse`, the threshold chosen from it will look excellent
and fail on contact with anything else. So the searches here include the things
that make benign traffic awkward for a payload-based detector: apostrophes in
product names, quoted phrases, hyphens and dashes, URL-encoded characters,
comparison operators, long queries, and words that happen to contain SQL
keywords ("ordered", "selection", "android"). Those are the rows that generate
false positives, and leaving them out would be calibrating against a strawman.

Traffic is paced. Each client stays well under 30 requests per minute, because
above that RATE_ELEVATED fires and the request stops being benign as far as the
system is concerned -- correctly. A benign generator that trips the rate rules
is measuring bursty traffic, not normal traffic.
"""

import argparse
import time

from common import BENIGN, Client, Recorder, preflight, rng

# Ordinary shopping queries, including the ones that are inconvenient for a
# detector: punctuation, encodings, and words containing SQL keywords.
SEARCHES = [
    "laptop", "mouse", "keyboard", "monitor",
    "wireless mouse", "usb-c hub", "27 inch monitor", "gaming keyboard",
    "laptop stand", "monitor arm", "hdmi cable", "webcam 1080p",
    # apostrophes: the single most common benign source of a SQLi signal
    "logitech's mx master", "children's tablet", "o'brien headphones",
    # quoted phrases and comparison operators, as a search UI would send them
    '"mechanical keyboard"', "price < 100", "rating >= 4",
    "laptop & charger", "monitor + stand",
    # words that contain SQL keywords as substrings
    "ordered list organiser", "selection of cables", "android charger",
    "updated firmware", "creative mouse pad", "delete key replacement",
    # encoded and spaced input, as produced by a real browser
    "laptop%20bag", "usb   hub", "  keyboard  ",
    # longer natural-language queries
    "best laptop for university student under 1000",
    "which monitor works with macbook pro 2023",
    # non-ASCII, which exercises the code-point handling in both extractors
    "café keyboard", "naïve mouse", "日本語 keyboard",
]

BROWSE_IDS = ["101", "102", "203", "417", "888"]


def run(clients=8, rounds=4, seed=42, pause=0.35, recorder_name="benign"):
    r = rng(seed)
    with Recorder(recorder_name) as rec:
        sessions = []
        for i in range(clients):
            c = Client(i)
            user = f"shopper{i:02d}_{rec.run_id[-6:]}"
            pw = f"pw-{user}-8842"
            c.register(user, pw, rec)
            time.sleep(pause)
            status = c.login(user, pw, rec, label=BENIGN)
            if status != 200:
                print(f"  client {c.ip}: login returned {status}")
            sessions.append((c, user, pw))
            time.sleep(pause)

        for round_no in range(rounds):
            for c, user, pw in sessions:
                # a couple of searches, then look at an order: a plausible
                # browse-then-act session rather than uniform request spam
                for q in r.sample(SEARCHES, 2):
                    c.search(q, rec, label=BENIGN)
                    time.sleep(pause * r.uniform(0.6, 1.6))
                c.get(f"/api/orders/{r.choice(BROWSE_IDS)}", rec,
                      payload="", label=BENIGN)
                time.sleep(pause * r.uniform(0.6, 1.6))
            # a returning user logs in again between rounds
            if round_no % 2 == 1:
                c, user, pw = sessions[round_no % len(sessions)]
                c.login(user, pw, rec, label=BENIGN)
                time.sleep(pause)

        print("  " + rec.summary())
        if rec.rows:
            fp = rec.blocked / rec.rows * 100
            print(f"  false positive rate on benign traffic: {fp:.1f}%")
        return rec.path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clients", type=int, default=8)
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pause", type=float, default=0.35,
                    help="base think-time between requests, seconds")
    ap.add_argument("--allow-dirty-window", action="store_true")
    args = ap.parse_args()

    preflight(require_clean_window=not args.allow_dirty_window)
    print(f"benign traffic: {args.clients} clients x {args.rounds} rounds")
    run(args.clients, args.rounds, args.seed, args.pause)


if __name__ == "__main__":
    main()
