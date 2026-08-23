# A5 spike — does the interrupt mechanic survive a `Graph`?

**Verdict: yes, unchanged.** Run `python -m spikes.a5_graph_interrupt.run` from
`agent/`. Exit code 0 means the architecture's central assumption still holds.

## The question

A1 proved a bare `Agent` can be interrupted mid tool call, suspended to disk, and
resumed in a *different OS process*. A5 puts every agent inside a `GraphBuilder`
graph, and the whole design assumes that changes nothing.

If it were false we would need a different architecture, so it was worth
answering before building the real graph rather than after.

## What was run

Two nodes, a miniature of the real graph:

```
triage (file_record, SILENT)  ->  negotiator (cancel_subscription, CONFIRM)
```

Three scenarios, each across two genuinely separate processes: **approve**,
**deny**, and **approve_always**. All three pass.

## What it established

1. **A tool call inside a node interrupts the whole graph.** The result comes
   back `Status.INTERRUPTED`, and `GraphResult.interrupts` carries the same
   `Interrupt` objects A1 saw. `card_from_interrupt` needs no changes.
2. **Interrupt ids are unchanged**, still
   `v1:before_tool_call:{toolUseId}:{uuid5}` — so `decision_id_for` and the whole
   A3 gate work as-is.
3. **A resumed graph replays only the interrupted node.** Nodes that completed
   before the suspension stay completed. Their silent actions are *not* repeated,
   which the spike asserts explicitly (`silent actions already logged = 1`, still
   1 after the resume). Had this gone the other way, every activity trail would
   double-count and the autonomy rate would be computed off inflated numbers.
4. **Resuming is the same payload, handed to the graph instead of the agent**:
   `graph([{"interruptResponse": {...}}])`. Still a list. A null `response` still
   strands the run forever.
5. **Policy learning works from inside a node** — `approve_always` on a graph
   interrupt creates the same `Policy` it does for a bare agent.

## The two constraints it turned up

Both are silent failures, which is why `test_a5_graph_spike.py` pins them.

**`PolicyHook` goes on each node `Agent`, never on the `GraphBuilder`.**
`BeforeToolCallEvent` is dispatched by the tool executor through the *agent's*
hook registry (`strands/tools/executors/_executor.py`). A provider registered via
`GraphBuilder.set_hook_providers([...])` only ever receives the multi-agent
events — `BeforeNodeCallEvent` and friends. A `PolicyHook` registered there would
gate **nothing at all** while looking entirely correct in review, in tests that
only check construction, and in a demo right up until the first real tool call.

**The `SessionManager` goes on the `GraphBuilder`, never on a node `Agent`.**
Strands raises `ValueError("Session persistence is not supported for Graph agents
yet.")` if a node executor carries its own. This is a change from A1, where the
session manager sat on the `Agent`. The graph's session persists each interrupted
node's messages, state and interrupt state on its behalf.

## One bug it exposed in our own code

Sharing a single `PolicyHook` across nodes is correct and deliberate — it
accumulates the run's verdicts and learned policies. But the specialists run **in
parallel**, and `ScriptedModel` was generating `toolUseId`s from the script index
alone, so every node's first tool call got the id `tooluse_qh_0`.

The hook keys its pending-call table — and every derived `decision_id` — on that
id, so one node's audit entry silently overwrote another's, and two unrelated
actions could have collided on a single decision card. Fixed by giving each
`ScriptedModel` a per-instance nonce (`models.py`). A real provider guarantees
uniqueness itself; the scripted one has to do it deliberately.

## Files

| File | What it is |
|---|---|
| `graph_fixture.py` | The two-node graph, built identically by both processes |
| `step1_start.py` | Process 1: run until the gate interrupts, persist the card, exit |
| `step2_resume.py` | Process 2: answer it, resume the graph, check what ran |
| `run.py` | Driver — spawns real subprocesses, runs all three scenarios |

Kept as executable documentation and as a regression test
(`agent/tests/test_a5_graph_spike.py`). If a Strands upgrade breaks any of this,
that test fails on the day it happens rather than in week three.
