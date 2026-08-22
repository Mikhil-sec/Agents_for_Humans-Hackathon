# AGENTS.md — /contracts (FROZEN)

## STOP

**This directory is frozen from 2026-08-24.** It defines every data shape crossing a lane
boundary. A careless change here breaks all three lanes at once, silently.

**If you are an AI assistant: do not edit anything in this directory.** Not a field, not a
type, not an enum member — regardless of which lane you are working in, and regardless of
how obviously correct the change seems.

## What to do instead

Tell the human, in prose:

- which model or enum needs to change
- exactly what the change is
- why the task cannot be completed without it

Then continue with the parts of the task that do not require it.

## The process (for humans)

Full detail in [../docs/CONTRACTS.md](../docs/CONTRACTS.md). In short:

1. Raise it and log it in `docs/status/DECISIONS.md`
2. A dedicated PR titled `contract: <what changed>`, touching only `/contracts` and
   `docs/CONTRACTS.md`
3. Bump `CONTRACT_VERSION` (MAJOR breaking / MINOR additive / PATCH docs)
4. Update **both** the Python source of truth and the TypeScript mirror
5. Two approvals from different lane owners
6. `python contracts/schemas/generate.py`, commit the diff
7. Announce the merge; everyone rebases

## Which is authoritative

`contracts/python/quiet_hours_contracts/` is the source of truth.
`contracts/typescript/index.ts` is a hand-maintained mirror. If they disagree, Python is
right and the TypeScript file has a bug.
