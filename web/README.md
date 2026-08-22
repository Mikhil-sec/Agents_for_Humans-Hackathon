# web — the decision inbox (Lane B)

Not yet scaffolded. **Lane B bootstraps it**, so that the tooling choices are made
by the person who owns them:

```bash
cd web
npx create-next-app@latest . --typescript --tailwind --app --eslint --src-dir=false
npm install
```

Then read [AGENTS.md](AGENTS.md) and [../docs/lanes/LANE_B_WEB.md](../docs/lanes/LANE_B_WEB.md)
before writing any UI.

## The one rule

**This is not a chat app.** It is a decision inbox that is usually empty. The best
screenshot of this product is the empty state: *"Nothing needs you today."*

## Screens

| Route | Purpose |
|---|---|
| `/` | Today — pending decision cards, or the empty state |
| `/activity` | The audit trail — everything the agent did, and why |
| `/policies` | Rules you have granted, with a one-click revoke |
| `/insights` | The autonomy chart — the demo's headline visual |

## Types

Import from `contracts/typescript/index.ts`. Never redeclare an API payload type
locally. Add a path alias in `tsconfig.json`:

```json
{ "compilerOptions": { "paths": { "@contracts": ["../contracts/typescript/index.ts"] } } }
```

## Backend

Point `NEXT_PUBLIC_API_URL` at the API running with `QH_BACKEND=fixtures`. You never
need the agent running to build any screen here.
