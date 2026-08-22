"""`make agent` - run one full cycle locally in mock mode.

Must work with **zero credentials**. This is what a hackathon judge runs, and it
is the fastest inner loop for Lane A.

    QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run
    QH_PROVIDER_MODE=mock python -m quiet_hours_agent.local_run --replay-weeks 4

The `--replay-weeks` flag replays the seeded four-week history to generate the
autonomy curve the demo chart displays. See docs/DEMO_SCRIPT.md.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quiet-hours-agent")
    parser.add_argument("--household", default="hh_demo")
    parser.add_argument(
        "--replay-weeks",
        type=int,
        default=0,
        help="Replay N weeks of seeded history to produce the autonomy curve.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )

    mode = os.environ.get("QH_PROVIDER_MODE", "mock")
    if mode != "mock" and not os.environ.get("AWS_REGION"):
        print("live mode needs AWS_REGION; set QH_PROVIDER_MODE=mock to run offline", file=sys.stderr)
        return 2

    print(f"Quiet Hours - household={args.household} mode={mode}")
    raise SystemExit("Lane A: implement the run loop. See docs/lanes/LANE_A_AGENT.md (A1-A7).")


if __name__ == "__main__":
    raise SystemExit(main())
