"""A5 spike driver — the A1 question, asked again of a `Graph`.

A1 proved a bare `Agent` can be interrupted mid tool call, suspended to disk, and
resumed in a different OS process. A5 puts every agent inside a `GraphBuilder`
graph, and the whole architecture assumes that changes nothing. This spike is
what makes that an observation rather than an assumption.

Like A1 it spawns genuinely separate processes rather than importing the steps,
because a shared interpreter would quietly hide any state that failed to persist.

Usage:  python -m spikes.a5_graph_interrupt.run

Exit code 0 means the interrupt mechanic survives a graph.
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
    completed = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=str(AGENT_DIR),
        env=child_env(),
        check=False,
        # Windows: pytest's capture leaves an invalid stdin handle behind, which
        # kills the child with `WinError 6`. Same fix A1 needed.
        stdin=subprocess.DEVNULL,
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

    code1 = run_step("spikes.a5_graph_interrupt.step1_start")
    print(f"\n  -> process 1 exited with {code1}")
    if code1 != 0:
        return False

    code2 = run_step("spikes.a5_graph_interrupt.step2_resume", choice)
    print(f"\n  -> process 2 exited with {code2}")
    return code2 == 0


def main() -> int:
    results = {
        "approve": scenario("interrupt inside a graph node -> approved in a new process", "approve"),
        "deny": scenario("interrupt inside a graph node -> declined, tool never runs", "deny"),
        "approve_always": scenario(
            "approve_always inside a graph node -> a policy is learned", "approve_always"
        ),
    }

    print("\n" + "=" * 72)
    print("A5 SPIKE RESULT")
    print("=" * 72)
    for name, ok in results.items():
        print(f"  {name:<16} {'PASS' if ok else 'FAIL'}")

    everything_passed = all(results.values())
    print(
        "\n  VERDICT: interrupts propagate out of a Graph and resume across processes."
        if everything_passed
        else "\n  VERDICT: the graph does NOT preserve the interrupt mechanic — see above."
    )
    return 0 if everything_passed else 1


if __name__ == "__main__":
    sys.exit(main())
