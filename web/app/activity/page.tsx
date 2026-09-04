'use client';

/**
 * Activity — the audit trail.
 *
 * Everything the agent did, autonomous or not, with the reasoning that produced
 * it. This is the screen that makes the whole thing trustworthy: an agent that
 * acts on its own is only acceptable if every action it took is here, in one
 * list, explainable after the fact.
 *
 * The filter is a view onto one trail, never two separate lists — "handled
 * silently" and "you decided" are the same history seen from two angles.
 */

import { useMemo, useState } from 'react';
import Link from 'next/link';
import type { ActivityEntry, DecisionCard, Policy } from '@contracts';
import { formatMoney } from '@contracts';
import { getActivity, getAllDecisions, getPolicies } from '@/lib/api';
import { formatDayHeading, formatTime } from '@/lib/format';
import { useResource } from '@/lib/useResource';
import { useTimezone } from '@/components/HouseholdContext';
import { RiskPill } from '@/components/RiskPill';
import { ErrorState, RowSkeleton, SectionEmpty } from '@/components/States';

type Filter = 'all' | 'silent' | 'decided';

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'Everything' },
  { id: 'silent', label: 'Handled silently' },
  { id: 'decided', label: 'You decided' },
];

export default function ActivityPage() {
  const [filter, setFilter] = useState<Filter>('all');
  const activity = useResource(() => getActivity(), []);
  // Loaded alongside so an expanded row can show the evidence behind a decision
  // and name the rule that permitted an autonomous action. A trail that says
  // "handled automatically" without saying which rule allowed it is not an audit
  // trail.
  const decisions = useResource(getAllDecisions, []);
  const policies = useResource(() => getPolicies(true), []);
  const timezone = useTimezone();

  const cardsById = useMemo(() => {
    const index = new Map<string, DecisionCard>();
    for (const card of decisions.data?.items ?? []) index.set(card.decision_id, card);
    return index;
  }, [decisions.data]);

  const policiesById = useMemo(() => {
    const index = new Map<string, Policy>();
    for (const policy of policies.data?.items ?? []) index.set(policy.policy_id, policy);
    return index;
  }, [policies.data]);

  const entries = (activity.data?.items ?? []).filter((entry) => {
    if (filter === 'silent') return entry.was_autonomous;
    if (filter === 'decided') return !entry.was_autonomous;
    return true;
  });

  const days = useMemo(() => groupByDay(entries, timezone), [entries, timezone]);
  const silentCount = (activity.data?.items ?? []).filter((e) => e.was_autonomous).length;
  const total = activity.data?.items.length ?? 0;

  return (
    <div>
      <header className="mb-6">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">Activity</p>
        <h1 className="mt-1.5 text-[26px] font-semibold leading-tight tracking-[-0.02em] text-ink">
          Everything Quiet Hours did
        </h1>
        <p className="mt-2 max-w-lg text-[15px] leading-relaxed text-muted">
          {total > 0 ? (
            <>
              {silentCount} of {total} actions were handled without interrupting you. Every one of
              them is here, with the reasoning behind it.
            </>
          ) : (
            'Nothing has happened yet.'
          )}
        </p>
      </header>

      <div className="mb-5 flex gap-1 border-b border-line" role="tablist">
        {FILTERS.map((option) => (
          <button
            key={option.id}
            role="tab"
            aria-selected={filter === option.id}
            onClick={() => setFilter(option.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm transition-colors ${
              filter === option.id
                ? 'border-ink font-medium text-ink'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {activity.loading ? (
        <div>
          <RowSkeleton />
          <RowSkeleton />
          <RowSkeleton />
          <RowSkeleton />
        </div>
      ) : activity.error ? (
        <ErrorState error={activity.error} onRetry={() => void activity.reload()} />
      ) : entries.length === 0 ? (
        <SectionEmpty>
          {filter === 'decided'
            ? 'You have not had to decide anything. That is the idea.'
            : 'Nothing to show here yet.'}
        </SectionEmpty>
      ) : (
        <div className="space-y-8">
          {days.map(([day, rows]) => (
            <section key={day}>
              <h2 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
                {day}
              </h2>
              <ul>
                {rows.map((entry) => (
                  <Row
                    key={entry.entry_id}
                    entry={entry}
                    timezone={timezone}
                    card={entry.decision_id ? cardsById.get(entry.decision_id) : undefined}
                    policy={entry.policy_id ? policiesById.get(entry.policy_id) : undefined}
                  />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function groupByDay(entries: ActivityEntry[], timezone: string): [string, ActivityEntry[]][] {
  const days = new Map<string, ActivityEntry[]>();
  for (const entry of entries) {
    const key = formatDayHeading(entry.occurred_at, timezone);
    const bucket = days.get(key);
    if (bucket) bucket.push(entry);
    else days.set(key, [entry]);
  }
  return [...days.entries()];
}

function Row({
  entry,
  timezone,
  card,
  policy,
}: {
  entry: ActivityEntry;
  timezone: string;
  card?: DecisionCard;
  policy?: Policy;
}) {
  const [open, setOpen] = useState(false);

  return (
    <li className="border-b border-line last:border-0">
      <button
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-baseline gap-3 py-3.5 text-left"
      >
        <span
          className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
            !entry.succeeded ? 'bg-danger' : entry.was_autonomous ? 'bg-calm' : 'bg-accent'
          }`}
          aria-hidden
        />
        <span className="flex-1 text-sm leading-relaxed text-ink">{entry.summary}</span>
        {entry.impact ? (
          <span className="tnum hidden text-sm font-medium text-calm sm:inline">
            {formatMoney(entry.impact)}
          </span>
        ) : null}
        <RiskPill risk={entry.risk} />
        <span className="tnum w-12 shrink-0 text-right text-xs text-muted">
          {formatTime(entry.occurred_at, timezone)}
        </span>
      </button>

      {open && (
        <div className="pb-5 pl-[18px] pr-2">
          <p className="text-sm leading-relaxed text-ink-soft">{entry.rationale}</p>

          <p className="mt-3 text-xs text-muted">
            {entry.was_autonomous ? 'Handled without asking you' : 'You decided this'}
            {policy ? (
              <>
                {' · permitted by your rule '}
                <Link
                  href="/policies"
                  className="underline decoration-line underline-offset-4 hover:text-ink"
                >
                  &ldquo;{policy.description}&rdquo;
                </Link>
              </>
            ) : entry.was_autonomous ? (
              ' · routine and reversible, so no rule was needed'
            ) : null}
          </p>

          {!entry.succeeded && entry.error ? (
            <p className="mt-3 rounded-lg bg-raised px-3 py-2 text-sm text-danger">{entry.error}</p>
          ) : null}

          {card && card.evidence.length > 0 ? (
            <div className="mt-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
                What it was based on
              </p>
              <ul className="mt-2 space-y-1.5">
                {card.evidence.map((item, index) => (
                  <li
                    key={`${item.signal_id}-${index}`}
                    className="rounded-lg bg-raised px-3 py-2 text-sm leading-relaxed text-ink-soft"
                  >
                    {item.excerpt}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <p className="mt-3 font-mono text-[11px] text-muted">
            run {entry.run_id.slice(0, 12)} · {entry.entry_id.slice(0, 12)}
          </p>
        </div>
      )}
    </li>
  );
}
