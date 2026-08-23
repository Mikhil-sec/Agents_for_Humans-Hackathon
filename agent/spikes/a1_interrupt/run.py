"""A1 spike driver — runs the whole thing as genuinely separate OS processes.

The point of A1 is durability across a process boundary, so this does not import
the steps and call them. It spawns them with `subprocess`, exactly as a Lambda
invocation and a later resume invocation would be separated.

Usage:  python -m spikes.a1_interrupt.run

Exit code 0 means the interrupt mechanic works as the architecture assumes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENT_DIR = REPO_ROOT / "agent"
CONTRACTS_DIR = REPO_ROOT / "contracts" / "python"
ARTIFACTS = Path(__file__).parent / "artifacts"


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    parts = [str(CONTRACTS_DIR), str(AGENT_DIR)] + ([existing] if existing else [])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["QH_PROVIDER_MODE"] = "mock"
    return env


def run_step(module: str, *args: str) -> int:
    """Run one step in its own process and stream its output."""
    completed = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=str(AGENT_DIR),
        env=child_env(),
        check=False,
    )
    return completed.returncode


def wipe() -> None:
    if ARTIFACTS.exists():
        shutil.rmtree(ARTIFACTS)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)


def scenario(name: str, choice: str) -> bool:
    print("\n" + "=" * 72)
    print(f"SCENARIO: {name}")
    print("=" * 72)

    wipe()

    code1 = run_step("spikes.a1_interrupt.step1_start")
    print(f"\n  -> process 1 exited with {code1}")
    if code1 != 0:
        return False

    code2 = run_step("spikes.a1_interrupt.step2_resume", choice)
    print(f"\n  -> process 2 exited with {code2}")
    return code2 == 0


def main() -> int:
    results = {
        "approve": scenario("user approves -> tool runs in the second process", "approve"),
        "deny": scenario("user declines -> tool never runs", "deny"),
    }

    print("\n" + "=" * 72)
    print("A1 SPIKE RESULT")
    print("=" * 72)
    for name, ok in results.items():
        print(f"  {name:<10} {'PASS' if ok else 'FAIL'}")

    everything_passed = all(results.values())
    print(
        "\n  VERDICT: the Strands interrupt mechanic works across process boundaries."
        if everything_passed
        else "\n  VERDICT: the mechanic did NOT behave as assumed — see failures above."
    )
    return 0 if everything_passed else 1


if __name__ == "__main__":
    sys.exit(main())
