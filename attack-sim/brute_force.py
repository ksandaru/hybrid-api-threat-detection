import argparse
import time

from common import ATTACK, BENIGN, Client, Recorder, preflight, rng

WORDLIST = [
    "123456", "password", "12345678", "qwerty", "abc123", "111111",
    "letmein", "welcome", "admin", "iloveyou", "monkey", "dragon",
    "sunshine", "princess", "football", "password1", "123123", "000000",
    "qwerty123", "1q2w3e4r", "trustno1", "hunter2", "master", "shadow",
    "superman", "batman", "passw0rd", "starwars", "whatever", "zaq12wsx",
]


def run(attempts=30, seed=42, pause=0.12, recorder_name="brute_force"):
    r = rng(seed)
    with Recorder(recorder_name) as rec:
        attacker = Client(0)
        victim = f"victim_{rec.run_id[-6:]}"
        real_pw = f"S3cure-{victim}-real"

        # register the victim from a *different* source, so the attacker's
        # window contains only the attack, not the setup
        setup = Client(200)
        setup.register(victim, real_pw, rec)
        time.sleep(pause)

        first_block = None
        guesses = list(WORDLIST)[:attempts]
        for i, pw in enumerate(guesses, start=1):
            status = attacker.login(victim, pw, rec, label=ATTACK,
                                    attack_type="brute_force")
            if status == 403 and first_block is None:
                first_block = i
            time.sleep(pause)

        print("  " + rec.summary())
        if first_block:
            print(f"  blocking began at attempt {first_block} of {len(guesses)}")
        else:
            print("  never blocked -- check DETECTION_MODE is not 'off'")
        return rec.path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attempts", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pause", type=float, default=0.12)
    ap.add_argument("--allow-dirty-window", action="store_true")
    args = ap.parse_args()

    preflight(require_clean_window=not args.allow_dirty_window)
    print("brute-force attack traffic")
    run(args.attempts, args.seed, args.pause)


if __name__ == "__main__":
    main()
