"""Regression guard for the interrupt mechanic *inside a graph*.

A1 proved a bare `Agent` can be suspended mid tool call and resumed in another
process. A5 put every agent inside a `Graph`, and the whole architecture assumes
that changed nothing. This is the test that fails loudly if an SDK upgrade makes
that assumption false — which would be a design problem, not a bug fix, so it is
worth knowing on the day it happens rather than in week three.

Slow by unit-test standards (it spawns real subprocesses) but a *cross-process*
guarantee cannot honestly be tested in-process.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from spikes.a5_graph_interrupt import run as spike_run


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
    [("approve", True), ("deny", False), ("approve_always", True)],
)
def test_a_graph_interrupt_survives_a_process_exit(
    clean_artifacts, choice: str, should_execute: bool
):
    """A tool call inside a graph node suspends the whole graph, and resumes."""
    start = _run("spikes.a5_graph_interrupt.step1_start")
    assert start.returncode == 0, f"process 1 failed:\n{start.stdout}\n{start.stderr}"
    assert "graph status      = Status.INTERRUPTED" in start.stdout

    # The node that ran *before* the interrupt must have completed and been
    # audited. A graph that rolled back completed work on suspension would make
    # every silent action provisional, and the activity trail a lie.
    assert "silent actions already logged = 1" in start.stdout

    resume = _run("spikes.a5_graph_interrupt.step2_resume", choice)
    assert resume.returncode == 0, f"process 2 failed:\n{resume.stdout}\n{resume.stderr}"
    assert "graph status      = Status.COMPLETED" in resume.stdout

    # step2 asserts the tool ran (or did not) and exits non-zero otherwise; this
    # pins the direction here too so a silently inverted check cannot pass.
    expected_policies = 1 if choice == "approve_always" else 0
    assert f"policies learned  = {expected_policies}" in resume.stdout
    assert should_execute == (choice != "deny")


def test_the_graph_wiring_the_spike_relies_on_is_still_what_the_sdk_requires():
    """The two constraints A5 discovered, asserted rather than remembered.

    Both are silent failures if they regress: a hook on the builder gates nothing
    while looking correct, and a session manager on a node raises only at build
    time. Pinning them here means an SDK change surfaces as a failing test rather
    than as an ungoverned tool call in a demo.
    """
    from strands import Agent
    from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry
    from strands.multiagent import GraphBuilder
    from strands.session import FileSessionManager

    from quiet_hours_agent.models import ScriptedModel

    # 1. A hook provider registered on the *builder* never receives tool-call
    #    events: the tool executor dispatches those through the agent's own
    #    registry. This is why `PolicyHook` goes on every node agent instead, and
    #    getting it wrong gates nothing while looking entirely correct.
    seen: list[type] = []

    class Spy(HookProvider):
        def register_hooks(self, registry: HookRegistry, **kwargs: object) -> None:
            seen.append(BeforeToolCallEvent)
            registry.add_callback(BeforeToolCallEvent, lambda event: None)

    builder = GraphBuilder()
    builder.add_node(Agent(model=ScriptedModel(), name="solo"), "solo")
    builder.set_entry_point("solo")
    builder.set_hook_providers([Spy()])
    built = builder.build()

    # The provider registered fine — it simply sits on a registry that tool calls
    # never reach.
    assert seen == [BeforeToolCallEvent]
    assert built.nodes["solo"].executor.hooks is not built.hooks

    # 2. A node executor may not carry its own session manager, so the session
    #    manager belongs on the builder.
    with pytest.raises(ValueError, match="Session persistence is not supported"):
        GraphBuilder().add_node(
            Agent(
                model=ScriptedModel(),
                name="with_session",
                session_manager=FileSessionManager(
                    session_id="qh-test-guard", storage_dir=str(spike_run.ARTIFACTS / "guard")
                ),
            ),
            "with_session",
        )
