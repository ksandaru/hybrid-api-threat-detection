import argparse
import time

from common import ATTACK, Client, Recorder, preflight, rng

PAYLOADS = {
    "tautology": [
        "' OR '1'='1",
        "' OR 1=1 --",
        "admin' OR '1'='1' --",
        "' OR 'x'='x",
        "1' OR '1'='1' #",
    ],
    "union": [
        "' UNION SELECT username, password FROM users --",
        "' UNION SELECT NULL, NULL, NULL --",
        "-1' UNION SELECT 1, version() --",
        "' UNION ALL SELECT table_name FROM information_schema.tables --",
    ],
    "comment": [
        "admin'--",
        "admin'#",
        "'; --",
        "root'/*",
    ],
    "stacked": [
        "'; DROP TABLE users --",
        "'; DELETE FROM products --",
        "1'; UPDATE users SET role='admin' --",
    ],
    "obfuscated": [
        "/**/OR/**/1=1",
        "'/**/OR/**/'1'='1",
        "%27%20OR%20%271%27%3D%271",          # url-encoded ' OR '1'='1
        "' oR '1'='1",                         # mixed case
        "'||'1'='1",                           # concatenation tautology
        "' OR/**/1/**/=/**/1 --",
    ],
    "blind": [
        "' AND SLEEP(5) --",
        "' AND 1=1 --",
        "' AND (SELECT COUNT(*) FROM users) > 0 --",
        "1' WAITFOR DELAY '0:0:5' --",
    ],
}


def run(clients=6, seed=42, pause=0.3, recorder_name="sqli"):
    r = rng(seed)
    with Recorder(recorder_name) as rec:
        pool = [Client(i) for i in range(clients)]
        # flatten to (subtype, payload), shuffled, so no single client sends one
        # whole family in a burst that the rate rules would catch as rate rather
        # than as SQLi
        items = [(st, p) for st, ps in PAYLOADS.items() for p in ps]
        r.shuffle(items)
        for idx, (subtype, payload) in enumerate(items):
            c = pool[idx % len(pool)]
            c.search(payload, rec, label=ATTACK, attack_type=f"sqli_{subtype}")
            time.sleep(pause * r.uniform(0.7, 1.3))

        print("  " + rec.summary())
        _per_family(rec.path)
        return rec.path


def _per_family(path):
    import csv
    from collections import Counter
    total, blocked = Counter(), Counter()
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            fam = row["attack_type"]
            if not fam.startswith("sqli_"):
                continue
            total[fam] += 1
            if row["blocked"] == "1":
                blocked[fam] += 1
    print("  detection rate by SQLi family (all runs in this CSV):")
    for fam in sorted(total):
        print(f"    {fam:22} {blocked[fam]:>3}/{total[fam]:<3} "
              f"{blocked[fam]/total[fam]*100:5.1f}%")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clients", type=int, default=6)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pause", type=float, default=0.3)
    ap.add_argument("--allow-dirty-window", action="store_true")
    args = ap.parse_args()

    preflight(require_clean_window=not args.allow_dirty_window)
    print("SQLi attack traffic")
    run(args.clients, args.seed, args.pause)


if __name__ == "__main__":
    main()
