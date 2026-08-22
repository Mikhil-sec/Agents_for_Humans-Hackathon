# AGENTS.md — /integrations (Lane C)

Root rules: [../AGENTS.md](../AGENTS.md). Protocol: [../docs/AI_AGENT_PROTOCOL.md](../docs/AI_AGENT_PROTOCOL.md).
Full brief: [../docs/lanes/LANE_C_INTEGRATIONS.md](../docs/lanes/LANE_C_INTEGRATIONS.md) — **read it before your first edit.**

## You are in Lane C

You may edit `/integrations`, `/fixtures`, `/infra`,
`docs/lanes/LANE_C_INTEGRATIONS.md` and `docs/status/PROGRESS_C.md`.

**You may not edit** `/agent`, `/api`, `/web` or `/contracts`.

## What lives here

Everything that touches the outside world, behind a provider interface with `mock` and
`live` implementations.

## Non-negotiables in this directory

1. **The live Gmail provider creates drafts and has no send path.** Do not implement one
   "for later". The absence of the code is the safety guarantee.
2. **The live payment provider creates scheduled payment requests, never unattended
   transfers.**
3. **Never commit a credential.** `.env.example` only; real values in Secrets Manager. If
   one is committed by accident, rotate it immediately and say so — do not quietly
   force-push.
4. **`base.py` is a contract with Lane A.** Treat changes to it with the same care as
   `/contracts`: announce first, change deliberately. Lane A codes against it from day one.
5. **Mock and live must satisfy the same test suite**, parametrised. Live tests skip
   without credentials.
6. **Mock mode must work with zero credentials, always.**

## Fixtures are a first-class deliverable

A judge experiences the fixtures, not the code. Thin fixtures make a brilliant agent look
boring. Seed real-looking UK merchants and amounts — never "Acme Corp" — and make sure the
four-week narrative in the lane brief actually produces the autonomy curve the demo needs.

## How to run

```bash
cd integrations && pip install -e .
python -m quiet_hours_integrations.mock.seed --out ../fixtures/
pytest -q
```

## Before you finish

Run `pytest`. Confirm `make demo` still works end to end. Append a dated entry to
`docs/status/PROGRESS_C.md`.
