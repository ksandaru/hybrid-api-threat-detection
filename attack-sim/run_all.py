"""
Run every Phase 8 generator in sequence, with a clean window between each.

The generators must not overlap. They share the API's 60-second behavioural
window, so a brute-force run started while benign traffic is still inside the
window would have its failure ratio diluted by the benign logins, and the
benign false-positive measurement would be contaminated by the attack. Running
them back to back without waiting would produce exactly the cross-talk the
per-generator preflight check is there to prevent.

So between generators this waits for the window to drain (or restarts the API,
which is faster). The result is four independent CSVs under evaluation/traffic/,
each measuring one traffic type against a stack that saw only that type.

This does not recalibrate the threshold; recalibrate_threshold.py does that from
the benign CSV afterwards. Keeping generation and calibration separate means the
benign traffic can be regenerated without silently moving the decision boundary.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from common import API_URL, api_ready, check_trust_proxy

HERE = Path(__file__).resolve().parent
GENERATORS = [
    ("benign_traffic.py", []),
    ("sqli_attack.py", []),
    ("brute_force.py", []),
    ("credential_stuffing.py", []),
]


def wait_for_clean_window(timeout=75, restart_after=8):
    """Wait for the 60s window to empty; offer a restart if it lingers."""
    start = time.time()
    while time.time() - start < timeout:
        ok, window = api_ready()
        if ok and window.get("events", 0) == 0:
            return True
        waited = time.time() - start
        if waited > restart_after and window.get("events", 0):
            print(f"  window still holds {window.get('events')} event(s) after "
                  f"{waited:.0f}s; restarting api to clear it")
            subprocess.run(["docker", "compose", "restart", "api"],
                           cwd=HERE.parent, capture_output=True)
            time.sleep(4)
            continue
        time.sleep(3)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    ok, _ = api_ready()
    if not ok:
        raise SystemExit(f"API at {API_URL} not answering. `docker compose up -d` first.")
    check_trust_proxy()

    print(f"running {len(GENERATORS)} generators against {API_URL}\n")
    for name, extra in GENERATORS:
        if not wait_for_clean_window():
            raise SystemExit(f"could not get a clean window before {name}")
        print(f"=== {name} ===")
        result = subprocess.run([args.python, str(HERE / name), *extra], cwd=HERE)
        if result.returncode != 0:
            raise SystemExit(f"{name} exited {result.returncode}")
        print()

    print("all generators complete. CSVs in evaluation/traffic/")
    print("next: python attack-sim/recalibrate_threshold.py")


if __name__ == "__main__":
    main()
