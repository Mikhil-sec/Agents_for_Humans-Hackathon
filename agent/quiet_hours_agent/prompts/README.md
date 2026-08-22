# Prompts

System prompts live here as `.md` files, one per agent node, never as inline
Python string literals.

**Why:** they are iterated on constantly, they are far easier to review as a diff
than as an escaped triple-quoted string, and a non-engineer can edit them.

## Files

| File | Node |
|---|---|
| `triage.md` | Classifies signals into findings |
| `bill_analyst.md` | Compares against merchant history, spots anomalies |
| `negotiator.md` | Drafts cancellations, disputes, retention pushback |
| `scheduler.md` | Calendar work and reminders |
| `brief.md` | Composes the digest |

## Writing rules

- **Never put a safety rule only in a prompt.** Safety lives in `policy.py`,
  which cannot be argued with. A prompt saying "always ask before spending money"
  is a nice-to-have on top of the gate, never the gate itself.
- Ask for structured output; pair each prompt with a `structured_output_model`.
- Tell the model to emit `evidence` for every finding — it is a required contract
  field, and the audit trail depends on it.
- Keep them short. Long prompts drift and cost tokens on every run.
