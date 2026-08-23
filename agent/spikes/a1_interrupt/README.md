# A1 — the interrupt spike

**Status: the mechanic works.** Verified 2026-08-22 against `strands-agents 1.53.0`.

This spike answers the one question the whole of Lane A rests on:

> Can a Strands agent stop mid-tool-call to ask the user something, **exit the
> process entirely**, and then have a *different* process resume that exact run
> and complete the tool call?

Yes. Both the approve and deny paths are proven.

## Run it

```bash
cd agent
PYTHONPATH="../contracts/python;." python -m spikes.a1_interrupt.run
```

No AWS credentials required — the model is a scripted stub (`scripted_model.py`),
because the spike is testing the interrupt plumbing, not the model.

## What each file does

| File | Role |
|---|---|
| `run.py` | Driver. Spawns the two steps as **real OS subprocesses**, twice (approve, deny). |
| `step1_start.py` | Process 1. Runs until the interrupt, persists a `DecisionCard`, exits. |
| `step2_resume.py` | Process 2. Rebuilds the agent from scratch, sends the answer, completes. |
| `spike.py` | Shared: the one governed tool, the approval hook, the agent factory. |
| `scripted_model.py` | A deterministic, credential-free `Model`. Emits one fixed tool call. |

`artifacts/` is regenerated on every run and is gitignored. It holds the session
store, the decision card, and `side_effects.log` — the ledger that proves *when*
the tool actually ran.

## The evidence

`side_effects.log` from an approve run. Note the two-second gap: process 1 had
already exited before the tool executed.

```
07:14:50.480 | PROCESS 1 start
07:14:50.585 | PROCESS 1 exit (suspended at interrupt)
07:14:52.021 | PROCESS 2 start (mode=approve)
07:14:52.096 | GATE resumed with answer={"choice": "approve", ...}
07:14:52.098 | EXECUTED cancel_subscription merchant=FitLife minor=3800
07:14:52.181 | PROCESS 2 exit (mode=approve)
```

## How it actually works

1. The hook calls `event.interrupt(name, reason=...)` on `BeforeToolCallEvent`.
   First time through, this **raises `InterruptException`**.
2. The event loop catches it, writes the session to disk, and returns an
   `AgentResult` with `stop_reason == "interrupt"` and a populated
   `result.interrupts`. **The process is not killed** — the runner gets control
   back cleanly and can persist the card.
3. `FileSessionManager` persists `_internal_state.interrupt_state`, which holds
   the pending interrupt *and* `context.tool_use_message` — the frozen tool call.
4. A new process builds an identical agent with the same `session_id`. Calling
   `agent([{"interruptResponse": ...}])` rehydrates that state, re-enters the
   hook, and this time `event.interrupt(...)` **returns the stored answer**
   instead of raising.
5. If the hook sets `event.cancel_tool = "<reason>"`, the tool never runs and the
   reason lands in a `toolResult` with `status: "error"`.

## Things worth knowing before A3

- **The interrupt id is deterministic**, not random:
  `v1:before_tool_call:{toolUseId}:{uuid5(NAMESPACE_OID, name)}`. The `toolUseId`
  is persisted in the session, so the id is stable across processes.
- **One interrupt per hook callback, and names must be unique** within a single
  tool call — two callbacks raising `qh-approval` is a `ValueError`.
- **The gate body runs twice** (once before the interrupt, once on resume). Any
  side effect in a hook must be idempotent. This is why the card is assembled by
  the runner from `result.interrupts[]`, not written inside the hook.
- **A response of `None` never resolves an interrupt.** `Interrupt.response is
  not None` is the check, so a null answer re-raises forever. Lane B must never
  post a null response.
- **Fail closed.** `is_approval()` treats anything it does not explicitly
  recognise as a denial.
