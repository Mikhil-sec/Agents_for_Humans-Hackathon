/**
 * Quiet Hours shared contracts — TypeScript mirror.
 *
 * FROZEN from 2026-08-24. Changes require a `contract:` PR with two approvals.
 * See docs/CONTRACTS.md.
 *
 * This file MUST stay in sync with `contracts/python/quiet_hours_contracts/`.
 * The Python package is the source of truth; this is the mirror. If they
 * disagree, Python wins and this file is the bug.
 *
 * Wire format is snake_case — it comes straight off the API. Do not add
 * camelCase variants here; if a component wants camelCase, map it in that
 * component.
 *
 * Lane B: import from here. Never redeclare an API payload type locally.
 */

export const CONTRACT_VERSION = '1.0.0' as const;

// ---------------------------------------------------------------------------
// Enums (string unions — they serialise identically to the Python str enums)
// ---------------------------------------------------------------------------

export type ProviderMode = 'mock' | 'live';

export type SignalKind = 'email' | 'transaction' | 'calendar_event' | 'statement';

export type FindingKind =
  | 'bill_due'
  | 'price_increase'
  | 'trial_converting'
  | 'duplicate_service'
  | 'unused_subscription'
  | 'unexpected_charge'
  | 'renewal_upcoming'
  | 'appointment_needs_reply'
  | 'usage_anomaly'
  | 'nothing_to_do';

export type ActionKind =
  | 'file_record'
  | 'tag_merchant'
  | 'update_budget_ledger'
  | 'set_reminder'
  | 'add_calendar_event'
  | 'pay_bill'
  | 'draft_email'
  | 'send_email'
  | 'cancel_subscription'
  | 'downgrade_plan'
  | 'reschedule_appointment'
  | 'dispute_charge'
  | 'close_account';

export type RiskTier = 'silent' | 'notify' | 'confirm' | 'never_auto';

export type DecisionStatus = 'pending' | 'resolved' | 'expired' | 'withdrawn';

export type DecisionChoice =
  | 'approve'
  | 'approve_always'
  | 'edit'
  | 'deny'
  | 'deny_always'
  | 'snooze';

export type RunStatus = 'running' | 'waiting_on_user' | 'completed' | 'failed';

export type RunTrigger = 'schedule' | 'manual' | 'resume';

export type PolicyScope = 'merchant' | 'category' | 'action_kind' | 'global';

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

/** ISO-8601 UTC timestamp, e.g. `2026-08-25T07:00:00Z`. */
export type IsoDateTime = string;

/**
 * Exact money. `amount_minor` is an integer count of minor units:
 * `{ amount_minor: 1799, currency: 'GBP' }` is £17.99.
 *
 * Never do arithmetic on this after dividing by 100. Format with `formatMoney`.
 */
export interface Money {
  amount_minor: number;
  currency: string;
}

export function formatMoney(m: Money, locale = 'en-GB'): string {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: m.currency,
  }).format(m.amount_minor / 100);
}

export interface Evidence {
  signal_id: string;
  excerpt: string;
  source_ref: string | null;
}

// ---------------------------------------------------------------------------
// Core entities
// ---------------------------------------------------------------------------

export interface Household {
  household_id: string;
  display_name: string;
  timezone: string;
  currency: string;
  digest_hour_local: number;
  quiet_hours_local: [number, number];
  created_at: IsoDateTime;
}

export interface Signal {
  signal_id: string;
  household_id: string;
  kind: SignalKind;
  occurred_at: IsoDateTime;
  ingested_at: IsoDateTime;
  source: string;
  subject: string | null;
  body: string | null;
  merchant: string | null;
  amount: Money | null;
  raw: Record<string, unknown>;
}

export interface Finding {
  finding_id: string;
  household_id: string;
  run_id: string;
  kind: FindingKind;
  title: string;
  detail: string;
  confidence: number;
  merchant: string | null;
  category: string | null;
  amount: Money | null;
  previous_amount: Money | null;
  due_at: IsoDateTime | null;
  evidence: Evidence[];
  created_at: IsoDateTime;
}

export interface ProposedAction {
  action_id: string;
  household_id: string;
  run_id: string;
  finding_id: string;
  kind: ActionKind;
  risk: RiskTier;
  summary: string;
  rationale: string;
  params: Record<string, unknown>;
  reversible: boolean;
  estimated_impact: Money | null;
  evidence: Evidence[];
  created_at: IsoDateTime;
}

// ---------------------------------------------------------------------------
// The interrupt surface
// ---------------------------------------------------------------------------

export interface DecisionOption {
  choice: DecisionChoice;
  label: string;
  description: string | null;
  is_default: boolean;
  /**
   * For `approve_always` / `deny_always`: the rule this would create, in plain
   * English. Render it — autonomy must never be granted invisibly.
   */
  creates_policy_preview: string | null;
}

export interface DecisionCard {
  decision_id: string;
  household_id: string;
  run_id: string;
  action_id: string;

  /** Strands interrupt linkage. Opaque to the web app — echo it back, never parse it. */
  session_id: string;
  interrupt_id: string;
  interrupt_name: string;

  headline: string;
  body: string;
  /** Why this needed a human. Always render this. */
  why_asking: string;
  options: DecisionOption[];
  amount: Money | null;
  estimated_impact: Money | null;
  evidence: Evidence[];

  status: DecisionStatus;
  urgency_deadline: IsoDateTime | null;
  created_at: IsoDateTime;
  resolved_at: IsoDateTime | null;
}

export interface DecisionResponse {
  decision_id: string;
  choice: DecisionChoice;
  edited_params: Record<string, unknown> | null;
  snooze_until: IsoDateTime | null;
  note: string | null;
  responded_at: IsoDateTime;
}

// ---------------------------------------------------------------------------
// Learned autonomy
// ---------------------------------------------------------------------------

export interface Policy {
  policy_id: string;
  household_id: string;
  scope: PolicyScope;
  action_kind: ActionKind | null;
  merchant: string | null;
  category: string | null;
  max_amount: Money | null;
  effect: 'auto_approve' | 'auto_deny';
  description: string;
  created_from_decision_id: string | null;
  created_at: IsoDateTime;
  revoked_at: IsoDateTime | null;
  times_applied: number;
  last_applied_at: IsoDateTime | null;
}

// ---------------------------------------------------------------------------
// Runs and audit trail
// ---------------------------------------------------------------------------

export interface ActivityEntry {
  entry_id: string;
  household_id: string;
  run_id: string;
  action_id: string | null;
  decision_id: string | null;
  occurred_at: IsoDateTime;
  summary: string;
  rationale: string;
  risk: RiskTier;
  was_autonomous: boolean;
  policy_id: string | null;
  succeeded: boolean;
  error: string | null;
  impact: Money | null;
}

export interface RunStats {
  signals_ingested: number;
  findings_created: number;
  actions_proposed: number;
  actions_autonomous: number;
  decisions_raised: number;
  policies_applied: number;
  estimated_annual_savings: Money | null;
}

export interface Run {
  run_id: string;
  household_id: string;
  trigger: RunTrigger;
  status: RunStatus;
  session_id: string;
  started_at: IsoDateTime;
  finished_at: IsoDateTime | null;
  stats: RunStats;
  error: string | null;
}

export interface DailyBrief {
  brief_id: string;
  household_id: string;
  run_id: string;
  generated_at: IsoDateTime;
  headline: string;
  handled_silently: string[];
  pending_decision_ids: string[];
  savings_this_month: Money | null;
  autonomy_rate: number;
}

// ---------------------------------------------------------------------------
// API envelopes
// ---------------------------------------------------------------------------

export interface ApiError {
  error: string;
  message: string;
  contract_version: string;
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
  contract_version: string;
}

/**
 * Share of actions handled without interrupting the user — the metric the whole
 * product optimises for, and the headline number in the demo.
 */
export function autonomyRate(stats: RunStats): number {
  if (stats.actions_proposed === 0) return 1;
  return stats.actions_autonomous / stats.actions_proposed;
}
