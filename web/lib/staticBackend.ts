/**
 * The static backend — the whole API, in the browser, for the hosted demo.
 *
 * GitHub Pages serves files and nothing else: there is no FastAPI process, no
 * DynamoDB, and no agent. This module stands in for all three so that the
 * deployed site is the *same product* a judge gets from `make demo` rather than
 * a set of screenshots.
 *
 * ## Why this exists rather than a pile of static JSON
 *
 * A static host ignores query strings. `/api/decisions?status=pending` and
 * `?status=all` would resolve to the same file, and `POST` is not a thing a file
 * server does at all. So the interception happens one level up: `api.ts` routes
 * every call through `request()`, and in static mode `request()` never touches
 * the network — it comes here instead. One branch, one module, and every
 * component above it is untouched and cannot tell the difference.
 *
 * ## It is a port, not a reimplementation
 *
 * Every behaviour below mirrors `api/app/backends/fixtures.py` and the route
 * modules beside it, deliberately and line for line where it matters: the same
 * `Page` envelope, the same pagination, the same error codes, the same rules for
 * expiring a stale card, learning a policy and recomputing the brief. Where the
 * two could drift, the Python is the source of truth and this file is wrong.
 *
 * **The consequence worth stating:** answering a card really does work here. It
 * leaves the inbox, it creates the rule the button previewed, it writes an
 * activity row, and the brief's headline and autonomy figure move. That is the
 * one interaction the entire product is about, and a hosted demo where the
 * buttons do nothing would be worse than no hosted demo.
 *
 * ## What it is not
 *
 * It is not the agent. Nothing here reasons, and no policy here decides anything
 * — the fixture data it serves was produced by a real agent run, offline, by
 * `make fixtures`. A visitor's answers live in their own tab and go when it
 * closes, which is the correct blast radius for a demo and is said plainly on
 * screen rather than left to be discovered.
 */

import type {
  ActivityEntry,
  DailyBrief,
  DecisionCard,
  DecisionResponse,
  Household,
  Money,
  Policy,
  Run,
} from '@contracts';
import { CONTRACT_VERSION } from '@contracts';
import { QuietHoursError } from './errors';

// The fixture set, imported rather than copied. `/fixtures` is Lane C's
// directory and these five files are what `make fixtures` writes, so the hosted
// demo and the local one are reading the same bytes and cannot disagree.
// Resolving them from outside the project root is the same mechanism the
// `@contracts` import already uses (`experimental.externalDir`).
import activityJson from '../../fixtures/activity.json';
import briefJson from '../../fixtures/daily_brief.json';
import decisionsJson from '../../fixtures/decisions.json';
import householdJson from '../../fixtures/household.json';
import policiesJson from '../../fixtures/policies.json';
import runsJson from '../../fixtures/runs.json';

/** Mirrors `api/app/config.py`. */
const DEFAULT_PAGE_SIZE = 50;
const MAX_PAGE_SIZE = 200;

/** Mirrors `FixturesBackend.EM_DASH`. Used to read a merchant off a headline. */
const EM_DASH = '—';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

/**
 * Mutable copies of the fixture data.
 *
 * Deep-cloned on first use because the imported JSON modules are shared and
 * frozen-by-convention: mutating them directly would leak one component's edit
 * into another's view of "the file on disk", and in dev it would survive a fast
 * refresh in ways a reader would never be able to explain.
 */
interface State {
  household: Household;
  decisions: DecisionCard[];
  runs: Run[];
  activity: ActivityEntry[];
  policies: Policy[];
  brief: DailyBrief | null;
}

let state: State | null = null;

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

/**
 * Where a visitor's answers live between page loads.
 *
 * **`sessionStorage`, not `localStorage`, and the difference is the point.** A
 * reload must not throw away the answer someone just gave — a card reappearing
 * after F5 reads as a broken demo. But the *next* person to open the link, in a
 * new tab, must get the seeded world back, card and all, because that card is
 * the demo. `sessionStorage` is scoped to one tab and dies with it, which is
 * exactly that pair of behaviours and is why it is worth the extra code over
 * plain module state.
 */
const SESSION_KEY = 'qh-static-demo-state';

function seeded(): State {
  return {
    household: clone(householdJson) as unknown as Household,
    decisions: clone(decisionsJson) as unknown as DecisionCard[],
    runs: clone(runsJson) as unknown as Run[],
    activity: clone(activityJson) as unknown as ActivityEntry[],
    policies: clone(policiesJson) as unknown as Policy[],
    brief: clone(briefJson) as unknown as DailyBrief,
  };
}

function restore(): State | null {
  // Private browsing throws on access rather than returning null, and a demo
  // that white-screens in an incognito window is a demo a judge cannot open —
  // which is exactly how they are told to check that a link is public.
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as State) : null;
  } catch {
    return null;
  }
}

function persist(): void {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(state));
  } catch {
    // Storage full, or blocked. The demo still works for this page view.
  }
}

function store(): State {
  if (state === null) state = restore() ?? seeded();
  return state;
}

/**
 * Put the seeded world back — the "start over" button, and what tests use.
 *
 * Deliberately available to the visitor: someone demonstrating this twice needs
 * the pending card back, and telling them to open a new tab is a worse answer
 * than a button.
 */
export function resetStaticState(): void {
  state = seeded();
  persist();
}

function nowIso(): string {
  return new Date().toISOString();
}

function newId(prefix: string): string {
  // `crypto.randomUUID` is not available on every browser the demo might be
  // opened in, and an id collision here is invisible until two rows merge in a
  // list. The fallback is not cryptographic and does not need to be.
  const random =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID().replace(/-/g, '')
      : Math.random().toString(16).slice(2) + Date.now().toString(16);
  return `${prefix}_${random.slice(0, 24)}`;
}

// ---------------------------------------------------------------------------
// The route layer — mirrors api/app/paging.py
// ---------------------------------------------------------------------------

function paginate<T>(items: T[], cursor: string | null, limit: number): unknown {
  const size = Math.max(1, Math.min(limit, MAX_PAGE_SIZE));
  const start = offsetOf(cursor);
  const window = items.slice(start, start + size);
  const end = start + window.length;
  return {
    items: window,
    next_cursor: end < items.length ? String(end) : null,
    contract_version: CONTRACT_VERSION,
  };
}

function offsetOf(cursor: string | null): number {
  if (cursor === null || cursor === '') return 0;
  const value = Number(cursor);
  if (!Number.isInteger(value) || value < 0) {
    throw new QuietHoursError('invalid_request', `malformed cursor '${cursor}'`, 400);
  }
  return value;
}

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

/**
 * A pending card past its deadline is `expired`, not `pending`.
 *
 * The agent does this on its next run; here nothing else would, and the inbox
 * must never offer a button for an opportunity that has already gone. Mirrors
 * `FixturesBackend._expire_stale`.
 */
function expireStale(): DecisionCard[] {
  const { decisions } = store();
  const now = Date.now();
  for (const card of decisions) {
    if (
      card.status === 'pending' &&
      card.urgency_deadline !== null &&
      Date.parse(card.urgency_deadline) <= now
    ) {
      card.status = 'expired';
    }
  }
  return decisions;
}

function listDecisions(status: string | null): DecisionCard[] {
  const cards = expireStale();
  const filtered = status === null ? cards : cards.filter((c) => c.status === status);
  return [...filtered].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

function requireDecision(id: string): DecisionCard {
  expireStale();
  const card = store().decisions.find((c) => c.decision_id === id);
  if (!card) throw new QuietHoursError('decision_not_found', `no decision ${id}`, 404);
  return card;
}

function listActivity(autonomous: boolean | null): ActivityEntry[] {
  const entries =
    autonomous === null
      ? store().activity
      : store().activity.filter((e) => e.was_autonomous === autonomous);
  return [...entries].sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at));
}

function listPolicies(includeRevoked: boolean): Policy[] {
  const all = store().policies;
  const wanted = includeRevoked ? all : all.filter((p) => p.revoked_at === null);
  return [...wanted].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

function listRuns(): Run[] {
  return [...store().runs].sort((a, b) => Date.parse(b.started_at) - Date.parse(a.started_at));
}

/**
 * The brief, with its counts recomputed.
 *
 * The stored brief is a snapshot of the run that produced it, so its counts go
 * stale the moment the user answers something. Recomputing them is what makes
 * the headline change from "One thing needs you" to "Nothing needs you today"
 * in front of the judge. Mirrors `FixturesBackend.latest_brief`.
 */
function latestBrief(): DailyBrief {
  const base = store().brief;
  if (base === null) {
    throw new QuietHoursError('brief_not_found', 'the agent has not produced a brief yet', 404);
  }
  const pending = listDecisions('pending').map((c) => c.decision_id);
  const silent = listActivity(true).map((e) => e.summary);
  const total = store().activity.length;
  return {
    ...base,
    pending_decision_ids: pending,
    handled_silently: silent.slice(0, 12),
    headline: headlineFor(pending.length),
    autonomy_rate: total ? silent.length / total : 1,
  };
}

function headlineFor(pending: number): string {
  if (pending === 0) return 'Nothing needs you today';
  if (pending === 1) return 'One thing needs you today';
  return `${pending} things need you today`;
}

// ---------------------------------------------------------------------------
// Writes
// ---------------------------------------------------------------------------

/**
 * Answer a card: resolve it, learn any rule it promised, log the answer.
 *
 * Mirrors `FixturesBackend.respond` including its validation, because rejecting
 * a choice the card never offered is a real rule and not a formality — the
 * options belong to the agent, and one it never proposed has no branch waiting
 * on the other side of the interrupt.
 */
function respond(decisionId: string, response: DecisionResponse): unknown {
  const card = requireDecision(decisionId);

  if (card.status !== 'pending') {
    throw new QuietHoursError(
      'decision_not_pending',
      `decision ${decisionId} is ${card.status}, not pending`,
      409,
    );
  }

  const offered = card.options.map((o) => o.choice);
  if (!offered.includes(response.choice)) {
    throw new QuietHoursError(
      'invalid_choice',
      `this card does not offer '${response.choice}'; it offers ${[...offered].sort().join(', ')}`,
      400,
    );
  }

  const snoozed = response.choice === 'snooze';
  card.status = snoozed ? 'pending' : 'resolved';
  card.resolved_at = snoozed ? null : response.responded_at;
  if (snoozed && response.snooze_until !== null) {
    card.urgency_deadline = response.snooze_until;
  }

  const policy = learnPolicy(card, response);
  store().activity.push(entryFor(card, response, policy));

  const run = store().runs.find((r) => r.run_id === card.run_id);
  const stillOpen = store().decisions.some(
    (c) => c.status === 'pending' && c.run_id === card.run_id,
  );
  const status: Run['status'] = stillOpen ? 'waiting_on_user' : 'completed';
  if (run) {
    run.status = status;
    run.finished_at = stillOpen ? null : nowIso();
    if (policy) run.stats.policies_applied += 1;
  }

  persist();

  return {
    run_id: card.run_id,
    status,
    decision_id: decisionId,
    choice: response.choice,
    contract_version: CONTRACT_VERSION,
  };
}

/**
 * Create the rule the button previewed — and only that rule.
 *
 * The description is `creates_policy_preview` **verbatim**: the user agreed to
 * those exact words, so the policies page must not show them different ones.
 * Autonomy is never granted invisibly, and never wider than what was on the
 * button. Mirrors `FixturesBackend._learn_policy`.
 */
function learnPolicy(card: DecisionCard, response: DecisionResponse): Policy | null {
  if (response.choice !== 'approve_always' && response.choice !== 'deny_always') return null;
  const option = card.options.find((o) => o.choice === response.choice);
  const preview = option?.creates_policy_preview;
  if (!preview) return null;

  const merchant = merchantOf(card);
  const policy: Policy = {
    policy_id: newId('pol'),
    household_id: card.household_id,
    scope: merchant ? 'merchant' : 'global',
    action_kind: null,
    merchant,
    category: null,
    max_amount: card.amount,
    effect: response.choice === 'approve_always' ? 'auto_approve' : 'auto_deny',
    description: preview.slice(0, 200),
    created_from_decision_id: card.decision_id,
    created_at: response.responded_at,
    revoked_at: null,
    times_applied: 0,
    last_applied_at: null,
  };
  store().policies.push(policy);
  return policy;
}

/**
 * The headline reads `Cancel subscription — PhotoCloud`. `DecisionCard` carries
 * no merchant field, so an em-dash split is the best available here — the same
 * compromise, and the same comment, as the Python.
 */
function merchantOf(card: DecisionCard): string | null {
  if (!card.headline.includes(EM_DASH)) return null;
  const tail = card.headline.split(EM_DASH).pop();
  return tail?.trim() || null;
}

function entryFor(
  card: DecisionCard,
  response: DecisionResponse,
  policy: Policy | null,
): ActivityEntry {
  const verbs: Record<string, string> = {
    approve: 'Approved',
    approve_always: 'Approved, and set a rule',
    edit: 'Approved with edits',
    deny: 'Declined',
    deny_always: 'Declined, and set a rule',
    snooze: 'Snoozed',
  };
  const verb = verbs[response.choice] ?? 'Answered';
  return {
    entry_id: newId('ent'),
    household_id: card.household_id,
    run_id: card.run_id,
    action_id: card.action_id,
    decision_id: card.decision_id,
    occurred_at: response.responded_at,
    summary: `${verb} ${EM_DASH} ${card.headline}`.slice(0, 160),
    rationale: response.note || card.why_asking,
    risk: 'confirm',
    was_autonomous: false,
    policy_id: policy ? policy.policy_id : null,
    succeeded: true,
    error: null,
    impact: card.estimated_impact,
  };
}

function revokePolicy(policyId: string): Policy {
  const policy = store().policies.find((p) => p.policy_id === policyId);
  if (!policy) throw new QuietHoursError('policy_not_found', `no policy ${policyId}`, 404);
  // Idempotent: revoking twice returns the same row, because the user pressing
  // the button again means the same thing both times.
  if (policy.revoked_at === null) policy.revoked_at = nowIso();
  persist();
  return policy;
}

/**
 * The demo button. A run over already-seen data finds nothing new, completes
 * immediately, and is recorded — which is exactly what the fixtures backend
 * does and exactly what the honest answer is: there is nothing new today.
 */
function triggerRun(): Run {
  const started = nowIso();
  const run: Run = {
    run_id: newId('run'),
    household_id: store().household.household_id,
    trigger: 'manual',
    status: 'completed',
    session_id: `qh-${store().household.household_id}-${newId('sess')}`,
    started_at: started,
    finished_at: started,
    stats: {
      signals_ingested: 0,
      findings_created: 0,
      actions_proposed: 0,
      actions_autonomous: 0,
      decisions_raised: 0,
      policies_applied: 0,
      estimated_annual_savings: null,
    },
    error: null,
  };
  store().runs.push(run);
  persist();
  return run;
}

/** Read by the run stream so its terminal frame matches the real one. */
export function staticGetRun(runId: string): Run | null {
  return store().runs.find((r) => r.run_id === runId) ?? null;
}

export function staticPendingFor(runId: string): DecisionCard[] {
  return listDecisions('pending').filter((c) => c.run_id === runId);
}

export function staticSavingsThisMonth(): Money | null {
  return latestBrief().savings_this_month;
}

// ---------------------------------------------------------------------------
// The router
// ---------------------------------------------------------------------------

/**
 * Route one call. The signature matches the `fetch` wrapper it replaces, so
 * `api.ts` needs a single branch and nothing above it changes.
 *
 * Unknown paths throw `backend_error` rather than returning undefined: a typo in
 * a path would otherwise surface as a blank screen three components away, and a
 * blank screen is indistinguishable from this product working correctly.
 */
export async function staticRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase();
  const [rawPath, rawQuery] = path.split('?');
  const query = new URLSearchParams(rawQuery ?? '');
  const cursor = query.get('cursor');
  const limit = Number(query.get('limit') ?? DEFAULT_PAGE_SIZE) || DEFAULT_PAGE_SIZE;

  const result = route<T>(method, rawPath, query, cursor, limit, init);

  // Resolve on a macrotask so callers see the same asynchrony they get from the
  // network. Components that set loading state before awaiting would otherwise
  // flash it for zero frames here and never be exercised in the hosted demo.
  return new Promise((resolve) => setTimeout(() => resolve(result), 0));
}

function route<T>(
  method: string,
  path: string,
  query: URLSearchParams,
  cursor: string | null,
  limit: number,
  init?: RequestInit,
): T {
  const segments = path.replace(/^\/+|\/+$/g, '').split('/');
  // Every route is under `/api`.
  if (segments[0] !== 'api') {
    throw new QuietHoursError('backend_error', `unrouted path ${path}`, 404);
  }
  const [, resource, first, second] = segments;

  if (resource === 'health' && method === 'GET') {
    return {
      status: 'ok',
      backend: 'static',
      contract_version: CONTRACT_VERSION,
    } as T;
  }

  if (resource === 'household' && method === 'GET') {
    return store().household as T;
  }

  if (resource === 'decisions') {
    if (!first && method === 'GET') {
      const status = query.get('status');
      const wanted = status === null || status === '' || status === 'all' ? null : status;
      if (wanted !== null && !['pending', 'resolved', 'expired', 'withdrawn'].includes(wanted)) {
        throw new QuietHoursError(
          'invalid_choice',
          `unknown status '${status}'; expected one of expired, pending, resolved, withdrawn`,
          400,
        );
      }
      return paginate(listDecisions(wanted), cursor, limit) as T;
    }
    if (first && second === 'respond' && method === 'POST') {
      const body = JSON.parse(String(init?.body ?? '{}')) as DecisionResponse;
      return respond(first, body) as T;
    }
    if (first && !second && method === 'GET') {
      return requireDecision(first) as T;
    }
  }

  if (resource === 'runs') {
    if (!first && method === 'GET') return paginate(listRuns(), cursor, limit) as T;
    if (!first && method === 'POST') return triggerRun() as T;
    if (first && !second && method === 'GET') {
      const run = staticGetRun(first);
      if (!run) throw new QuietHoursError('run_not_found', `no run ${first}`, 404);
      return run as T;
    }
  }

  if (resource === 'activity' && !first && method === 'GET') {
    const raw = query.get('autonomous');
    const autonomous = raw === null || raw === '' ? null : raw === 'true';
    return paginate(listActivity(autonomous), cursor, limit) as T;
  }

  if (resource === 'policies') {
    if (!first && method === 'GET') {
      return paginate(listPolicies(query.get('include_revoked') === 'true'), cursor, limit) as T;
    }
    if (first && method === 'DELETE') return revokePolicy(first) as T;
  }

  if (resource === 'brief' && first === 'latest' && !second && method === 'GET') {
    return latestBrief() as T;
  }

  throw new QuietHoursError('backend_error', `unrouted ${method} ${path}`, 404);
}
