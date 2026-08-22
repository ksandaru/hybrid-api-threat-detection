"""
Credential-stuffing attack generator.

Credential stuffing replays (username, password) pairs harvested from a breach
of one service against another, betting on password reuse. It differs from
brute force in its behavioural signature: instead of many passwords against one
username, it is many *distinct usernames* tried from one source, usually one
attempt each, so per-username failure counts stay low and only the breadth of
usernames gives it away. DISTINCT_USERNAMES / CREDENTIAL_STUFFING is the rule
written for exactly that shape.

**Ethics -- the load-bearing constraint of this file.** The credential pairs
are entirely synthetic, generated here from a fixed seed. They are not a real
leaked list, not a public breach corpus, not sampled or derived from real
credentials in any way. Using genuine leaked pairs would be both an ethics
violation and pointless: the attack is characterised by the *pattern* of many
usernames from one source, and invented pairs reproduce that pattern exactly.
The offline training corpus contains no credential-stuffing examples either
(recorded in Phase 1), so this generator is the only place this attack type is
represented, which makes its synthetic origin worth stating plainly.

A handful of the synthetic usernames are pre-registered with a *different*
password than the attacker tries, so the run includes the realistic case where
the account exists but the reused password does not match. None of the tried
passwords is ever a registered account's real password: no login here is meant
to succeed.
"""

import argparse
import time

from common import ATTACK, Client, Recorder, preflight, rng

FIRST = ["alex", "jordan", "sam", "taylor", "morgan", "casey", "riley",
         "jamie", "avery", "quinn", "drew", "reese", "skyler", "cameron",
         "hayden", "parker", "rowan", "emerson", "finley", "sage"]
LAST = ["smith", "jones", "lee", "brown", "wilson", "clark", "hall",
        "young", "king", "wright", "green", "adams", "baker", "nelson"]
REUSED = ["Summer2023!", "Password1!", "Welcome123", "Qwerty2024",
          "Football99", "Dragon2022", "iLoveYou1", "Sunshine!",
          "LetMeIn2023", "Master123", "Hockey#7", "Spring2024!"]


def synth_pairs(n, seed):
    """Deterministic synthetic credential pairs. No real data, ever."""
    r = rng(seed)
    seen, pairs = set(), []
    while len(pairs) < n:
        u = f"{r.choice(FIRST)}.{r.choice(LAST)}{r.randint(1, 99)}@example.com"
        if u in seen:
            continue
        seen.add(u)
        pairs.append((u, r.choice(REUSED)))
    return pairs


def run(count=40, seed=42, pause=0.15, preregister=6, recorder_name="credential_stuffing"):
    r = rng(seed)
    pairs = synth_pairs(count, seed)

    with Recorder(recorder_name) as rec:
        # pre-register a few of the targeted usernames with a DIFFERENT password,
        # from a separate source, so "account exists, reused password wrong" is
        # part of the mix rather than every attempt hitting an unknown user
        setup = Client(201)
        for u, _ in pairs[:preregister]:
            setup.register(u, f"actual-{u}-9931", rec)
            time.sleep(pause)

        attacker = Client(0)
        first_block = None
        for i, (u, pw) in enumerate(pairs, start=1):
            status = attacker.login(u, pw, rec, label=ATTACK,
                                    attack_type="credential_stuffing")
            if status == 403 and first_block is None:
                first_block = i
            time.sleep(pause * r.uniform(0.7, 1.3))

        print("  " + rec.summary())
        print(f"  {count} synthetic pairs, {preregister} pre-registered "
              f"(different password)")
        if first_block:
            print(f"  blocking began at distinct username #{first_block}")
        else:
            print("  never blocked -- check DETECTION_MODE is not 'off'")
        return rec.path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pause", type=float, default=0.15)
    ap.add_argument("--preregister", type=int, default=6)
    ap.add_argument("--allow-dirty-window", action="store_true")
    args = ap.parse_args()

    preflight(require_clean_window=not args.allow_dirty_window)
    print("credential-stuffing attack traffic (synthetic pairs)")
    run(args.count, args.seed, args.pause, args.preregister)


if __name__ == "__main__":
    main()
