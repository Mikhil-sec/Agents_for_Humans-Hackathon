"""Regression guard for the A1 interrupt mechanic.

A1 proved that a Strands interrupt survives a process exit. Everything in Lane A
is built on that assumption, so it is worth a test that fails loudly if an SDK
upgrade changes the behaviour.

This is slow by unit-test standards (it spawns four subprocesses) but it is the
only honest way to test a *cross-process* guarantee — doing it in-process would
test something we do not actually depend on.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from spikes.a1_interrupt import run as spike_run


def _run(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=str(spike_run.AGENT_DIR),
        env=spike_run.child_env(),
        capture_output=True,
        text=True,
        check=False,
        # Explicit: under pytest's capture on Windows the inherited stdin handle
        # is invalid and Popen fails with WinError 6.
        stdin=subprocess.DEVNULL,
    )


@pytest.fixture
def clean_artifacts():
    spike_run.wipe()
    yield
    spike_run.wipe()


@pytest.mark.parametrize(
    ("choice", "should_execute"),
    [("approve", True), ("deny", False)],
)
def test_interrupt_survives_a_process_exit(clean_artifacts, choice: str, should_execute: bool):
    """The tool must run only after the answer, and only in the second process."""
    start = _run("spikes.a1_interrupt.step1_start")
    assert start.returncode == 0, f"process 1 failed:\n{start.stdout}\n{start.stderr}"
    assert "stop_reason = 'interrupt'" in start.stdout

    ledger_after_start = (spike_run.ARTIFACTS / "side_effects.log").read_text(encoding="utf-8")
    assert "EXECUTED" not in ledger_after_start, "the tool ran before the user was asked"

    resume = _run("spikes.a1_interrupt.step2_resume", choice)
    assert resume.returncode == 0, f"process 2 failed:\n{resume.stdout}\n{resume.stderr}"

    ledger_after_resume = (spike_run.ARTIFACTS / "side_effects.log").read_text(encoding="utf-8")
    assert ("EXECUTED" in ledger_after_resume) is should_execute


def test_unrecognised_answers_fail_closed():
    """Anything we cannot read as an explicit approval must mean 'no'."""
    from spikes.a1_interrupt.spike import is_approval

    assert is_approval({"choice": "approve"})
    assert is_approval({"choice": "approve_always"})
    assert is_approval({"choice": "APPROVE"})

    assert not is_approval({"choice": "deny"})
    assert not is_approval({"choice": "snooze"})
    assert not is_approval({"choice": "maybe"})
    assert not is_approval({})
    assert not is_approval(None)
    assert not is_approval("")
    assert not is_approval(True)
    assert not is_approval(["approve"])
