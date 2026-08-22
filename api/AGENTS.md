# AGENTS.md — /api (Lane B)

Root rules: [../AGENTS.md](../AGENTS.md). Protocol: [../docs/AI_AGENT_PROTOCOL.md](../docs/AI_AGENT_PROTOCOL.md).
Full brief: [../docs/lanes/LANE_B_WEB.md](../docs/lanes/LANE_B_WEB.md) — **read it before your first edit.**

## You are in Lane B

You may edit `/api`, `/web`, `docs/lanes/LANE_B_WEB.md` and `docs/status/PROGRESS_B.md`.

**You may not edit** `/agent`, `/integrations`, `/infra`, `/fixtures` or `/contracts`.

## What lives here

FastAPI. It serves the decision inbox and, on `POST /decisions/{id}/respond`, resumes the
Strands session that is suspended at an interrupt.

## Non-negotiables in this directory

1. **Response models come from `quiet_hours_contracts`.** Never define a parallel schema.
2. **`session_id`, `interrupt_id` and `interrupt_name` are opaque.** Echo them back
   exactly as received. Never parse, construct or validate their internal shape — they
   belong to Strands and Lane A.
3. **Every response carries `contract_version`.** Do not remove it; the web app uses it to
   detect a stale deploy.
4. **`QH_BACKEND=fixtures` must always work.** It is how Lane B develops without the
   agent, and how the judge's `make demo` serves data.
5. Stable machine-readable `error` codes in `ApiError` — the web app switches on them.

## How to run

```bash
cd api && pip install -e ".[dev]"
QH_BACKEND=fixtures uvicorn app.main:app --reload --port 8000
pytest -q
```

## Before you finish

Run `pytest`. Hit the routes you changed. Append a dated entry to
`docs/status/PROGRESS_B.md` — append at the bottom, never rewrite earlier entries.
