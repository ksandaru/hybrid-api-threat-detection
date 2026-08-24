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

from common import API_URL, api_ready

HERE = Path(__file__).resolve().parent
GENERATORS = [
    ("benign_traffic.py", []),
    ("sqli_attack.py", []),
    ("brute_force.py", []),
    ("credential_stuffing.py", []),
]


def _can_restart_api():
    """Docker CLI reachable? False inside the sim container, which has no CLI."""
    try:
        subprocess.run(["docker", "version"], cwd=HERE.parent,
                       capture_output=True, timeout=10)
        return True
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return False


def wait_for_clean_window(timeout=120, restart_after=8):
    """
    Wait for the 60s window to empty.

    On the host, where the Docker CLI is reachable, a lingering window is
    cleared by restarting the api container -- faster than waiting it out. In
    the sim container there is no CLI, so it simply waits: the window is at most
    60 seconds, and the timeout allows for that plus margin.
    """
    can_restart = _can_restart_api()
    start = time.time()
    announced = False
    while time.time() - start < timeout:
        ok, window = api_ready()
        events = window.get("events", 0)
        if ok and events == 0:
            if announced:
                print("  window clear.")
            return True
        waited = time.time() - start
        if can_restart and waited > restart_after and events:
            print(f"  window still holds {events} event(s) after "
                  f"{waited:.0f}s; restarting api to clear it")
            subprocess.run(["docker", "compose", "restart", "api"],
                           cwd=HERE.parent, capture_output=True)
            time.sleep(4)
            continue
        # Print progress so a legitimate wait does not look like a hang. The
        # window drains within 60s of the last request to it (typically the
        # manual demo just before this), so this is expected, not stuck.
        remaining = max(0, timeout - waited)
        print(f"  waiting for detection window to drain: {events} event(s) "
              f"still in the last 60s (up to {remaining:.0f}s more)...", flush=True)
        announced = True
        time.sleep(5)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    ok, _ = api_ready()
    if not ok:
        raise SystemExit(f"API at {API_URL} not answering. `docker compose up -d` first.")
    # Deliberately no active trust-proxy probe here: a probe request would add
    # an event to the very window the first generator then waits to find clean,
    # manufacturing the delay it is trying to avoid. A misconfigured proxy shows
    # up plainly anyway, as benign traffic blocked near 90% instead of ~2%.

    print(f"running {len(GENERATORS)} generators against {API_URL}")
    print("(the first generator waits for a clean 60s window; if you just ran "
          "the manual demo, expect a short wait here)\n")
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
