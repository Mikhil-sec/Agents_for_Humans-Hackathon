## What this changes

<!-- One or two sentences. -->

## Lane

- [ ] A — `/agent`
- [ ] B — `/api`, `/web`
- [ ] C — `/integrations`, `/infra`, `/fixtures`
- [ ] `contract:` — needs two approvals from different lane owners

## Checklist

- [ ] Every file I changed is inside my lane (or this is a `contract:` PR)
- [ ] I did not touch `/contracts` (or this is a `contract:` PR and I bumped `CONTRACT_VERSION` and updated both Python and TypeScript)
- [ ] Tests pass for my lane
- [ ] `make demo` still works from a clean state
- [ ] I appended a dated entry to my `docs/status/PROGRESS_*.md`
- [ ] No secrets, tokens or `.env` files committed

## Verified how

<!-- What did you actually run? "Should work" is not a verification. If you could
     not verify something, say so here. -->
