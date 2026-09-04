'use client';

/**
 * Insights — the proof.
 *
 * Every other screen shows what the agent is doing. This one shows that it is
 * getting quieter, which is the claim the product actually makes. The numbers
 * are all measured: they come from `RunStats` the agent wrote at the end of each
 * run and from the audit trail, never from anything computed for display.
 *
 * The money sits in a stat tile rather than as a second line on the chart. It is
 * a different unit, and two y-axes on one plot is the fastest way to make a
 * truthful chart lie.
 */

import { useMemo } from 'react';
import type { Money } from '@contracts';
import { formatMoney } from '@contracts';
import { getActivity, getBrief, getPolicies, getRuns } from '@/lib/api';
import { formatPercent, totalMinor } from '@/lib/format';
import { useResource } from '@/lib/useResource';
import { AutonomyChart, weeksFromRuns } from '@/components/AutonomyChart';
import { useTimezone } from '@/components/HouseholdContext';
import { ErrorState, Skeleton } from '@/components/States';

export default function InsightsPage() {
  const runs = useResource(getRuns, []);
  const activity = useResource(() => getActivity(), []);
  const policies = useResource(() => getPolicies(), []);
  const brief = useResource(getBrief, []);
  const timezone = useTimezone();

  const weeks = useMemo(
    () => weeksFromRuns(runs.data?.items ?? [], timezone),
    [runs.data, timezone],
  );

  const entries = activity.data?.items ?? [];
  const silent = entries.filter((entry) => entry.was_autonomous);
  const rate = entries.length > 0 ? silent.length / entries.length : null;

  // Impact is realised money from the trail. `estimated_annual_savings` on a run
  // is a projection, and mixing a projection into a figure labelled "saved"
  // would be the one dishonest number on the page.
  const saved: Money | null =
    totalMinor(silent.map((entry) => entry.impact)) ?? brief.data?.savings_this_month ?? null;

  const firstWeek = weeks[0];
  const lastWeek = weeks[weeks.length - 1];
  const drop =
    firstWeek && lastWeek && firstWeek.raised > 0
      ? Math.round(((firstWeek.raised - lastWeek.raised) / firstWeek.raised) * 100)
      : null;

  const loading = runs.loading || activity.loading;
  const error = runs.error ?? activity.error;

  return (
    <div>
      <header className="mb-7">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">Insights</p>
        <h1 className="mt-1.5 text-[26px] font-semibold leading-tight tracking-[-0.02em] text-ink">
          Quiet Hours is asking you less
        </h1>
        <p className="mt-2 max-w-lg text-[15px] leading-relaxed text-muted">
          Every rule it learned came from an answer you gave. Nothing here was inferred silently,
          and you can revoke any of it in one click.
        </p>
      </header>

      {error ? (
        <ErrorState error={error} onRetry={() => void runs.reload()} />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat
              label="Handled silently"
              value={rate === null ? '—' : formatPercent(rate)}
              detail={`${silent.length} of ${entries.length} actions`}
              loading={loading}
              tone="calm"
            />
            <Stat
              label="Saved so far"
              value={saved ? formatMoney(saved) : '—'}
              detail="across every action in the trail"
              loading={loading}
              tone="calm"
            />
            <Stat
              label="Rules granted"
              value={String(policies.data?.items.length ?? 0)}
              detail="each revocable"
              loading={policies.loading}
            />
            <Stat
              label="Fewer interruptions"
              value={drop === null ? '—' : `${drop}%`}
              detail={
                firstWeek && lastWeek
                  ? `${firstWeek.raised} → ${lastWeek.raised} a week`
                  : 'needs two runs'
              }
              loading={loading}
            />
          </div>

          {loading ? (
            <Skeleton className="h-72 w-full" />
          ) : (
            <AutonomyChart weeks={weeks} />
          )}

          <section className="rounded-card border border-line bg-surface p-5">
            <h2 className="text-[15px] font-semibold text-ink">Why the line falls</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink-soft">
              When you answer &ldquo;always&rdquo;, Quiet Hours writes a rule in plain English and
              stops asking about that case. The policy engine that applies those rules is ordinary
              code, not a model — it cannot be talked out of a rule, and no rule can auto-approve
              something irreversible like disputing a charge or closing an account.
            </p>
            <p className="mt-3 text-sm leading-relaxed text-ink-soft">
              The line is not meant to reach zero. A new merchant, an unusual amount or anything
              irreversible will always come back to you — an agent that stopped asking entirely
              would have stopped being trustworthy.
            </p>
          </section>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  detail,
  loading,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  loading?: boolean;
  tone?: 'calm';
}) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      {/* Fixed label height so the four values sit on one line across the row,
          whatever the label wraps to at a narrow width. */}
      <p className="min-h-8 text-[11px] font-medium uppercase leading-4 tracking-[0.06em] text-muted">
        {label}
      </p>
      {loading ? (
        <Skeleton className="mt-2 h-7 w-16" />
      ) : (
        <p
          className={`tnum mt-1.5 text-[26px] font-semibold leading-none tracking-[-0.02em] ${
            tone === 'calm' ? 'text-calm' : 'text-ink'
          }`}
        >
          {value}
        </p>
      )}
      <p className="mt-2 text-xs leading-relaxed text-muted">{detail}</p>
    </div>
  );
}
