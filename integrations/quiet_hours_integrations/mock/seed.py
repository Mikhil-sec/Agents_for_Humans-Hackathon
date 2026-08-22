"""Generate the seeded four-week household history.

    python -m quiet_hours_integrations.mock.seed --out fixtures/

LANE C: this is the highest-leverage file you own. A judge experiences the
fixtures, not the code - thin data makes a capable agent look boring.

Build the data **backwards from the target curve**:

    week 1   ~9 decisions raised   ~4 handled silently
    week 2   ~6                    ~11
    week 3   ~3                    ~19
    week 4   ~2                    ~26

Scenarios to seed (each discoverable from the data alone, with no hints in the
prompts): the forgotten gym, the quiet price rise, the converting trial, the
duplicate cloud storage, the double charge, the routine electricity bill the
agent learns to stop asking about, the water-usage spike, the clashing dentist
appointment, and roughly 60% inbox noise it correctly ignores.

Full detail: docs/lanes/LANE_C_INTEGRATIONS.md.

Use real-looking UK merchants and amounts. Never "Acme Corp" - fake-looking data
makes the whole project read as a toy.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quiet-hours-seed")
    parser.add_argument("--out", type=Path, default=Path("fixtures"))
    parser.add_argument("--weeks", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260915, help="Deterministic output")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    raise SystemExit(
        "Lane C: implement the seeder. Build order step c/fixtures-full. "
        "Output must validate against quiet_hours_contracts models."
    )


if __name__ == "__main__":
    raise SystemExit(main())
