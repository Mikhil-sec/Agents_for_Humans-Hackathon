'use client';

/**
 * Today — the decision inbox.
 *
 * **This is not a chat app.** There is no composer and no message list. On a
 * good day this screen is empty, and the empty state is the best screenshot the
 * product has: "Nothing needs you today", with one quiet line underneath saying
 * what was handled while the user was not looking.
 *
 * The emotional target is relief. Everything below the fold exists to earn it —
 * an empty inbox only feels good if you can see what filled the silence.
 */

import { useCallback, useState } from 'react';
import Link from 'next/link';
import type { ActivityEntry, DecisionCard as Card, DecisionChoice } from '@contracts';
import { formatMoney } from '@contracts';
import { getActivity, getBrief, getPendingDecisions, respondToDecision } from '@/lib/api';
import { QuietHoursError } from '@/lib/errors';
import { formatTime } from '@/lib/format';
import { useResource } from '@/lib/useResource';
import { DecisionCard } from '@/components/DecisionCard';
import { RunButton } from '@/components/RunButton';
import { CardSkeleton, ErrorState, RowSkeleton, SectionHeading } from '@/components/States';
import { useTimezone } from '@/components/HouseholdContext';

export default function TodayPage() {
  const decisions = useResource(getPendingDecisions, []);
  const brief = useResource(getBrief, []);
  const silent = useResource(() => getActivity(true), []);
  const timezone = useTimezone();

  const [busyId, setBusyId] = useState<string | null>(null);
  const [failure, setFailure] = useState<QuietHoursError | null>(null);

  const reloadAll = useCallback(() => {
    void decisions.reload();
    void brief.reload();
    void silent.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function respond(card: Card, choice: DecisionChoice, extra?: { note?: string | null }) {
    setBusyId(card.decision_id);
    setFailure(null);
    try {
      await respondToDecision(card.decision_id, choice, extra);
      reloadAll();
    } catch (error) {
      // The answer may or may not have been saved. Say so, and reload rather
      // than optimistically removing a card that might still be pending.
      setFailure(
        error instanceof QuietHoursError
          ? error
          : new QuietHoursError('backend_error', String(error)),
      );
      reloadAll();
    } finally {
      setBusyId(null);
    }
  }

  const pending = decisions.data?.items ?? [];
  const handled = silent.data?.items ?? [];
  const savings = brief.data?.savings_this_month ?? null;

  return (
    <div className="space-y-12">
      <section>
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
              Today
            </p>
            <h1 className="mt-1.5 text-[26px] font-semibold leading-tight tracking-[-0.02em] text-ink">
              {decisions.loading ? (
                <span className="text-muted">Checking…</span>
              ) : pending.length === 0 ? (
                'Nothing needs you today.'
              ) : pending.length === 1 ? (
                'One thing needs you.'
              ) : (
                `${pending.length} things need you.`
              )}
            </h1>
            {!decisions.loading && (
              <p className="mt-2 max-w-md text-[15px] leading-relaxed text-muted">
                {handled.length > 0 ? (
                  <>
                    Quiet Hours handled {handled.length}{' '}
                    {handled.length === 1 ? 'thing' : 'things'} without asking
                    {savings ? (
                      <>
                        {' '}
                        and saved you{' '}
                        <span className="tnum font-medium text-calm">{formatMoney(savings)}</span>{' '}
                        this month
                      </>
                    ) : null}
                    .
                  </>
                ) : (
                  'Nothing has needed doing yet. You will hear from Quiet Hours when it does.'
                )}
              </p>
            )}
          </div>
          <RunButton onFinished={reloadAll} />
        </div>

        {failure ? (
          <div className="mb-5">
            <ErrorState error={failure} onRetry={reloadAll} />
          </div>
        ) : null}

        {decisions.loading ? (
          <CardSkeleton />
        ) : decisions.error ? (
          <ErrorState error={decisions.error} onRetry={() => void decisions.reload()} />
        ) : pending.length === 0 ? (
          <EmptyInbox />
        ) : (
          <div className="space-y-4">
            {pending.map((card) => (
              <DecisionCard
                key={card.decision_id}
                card={card}
                busy={busyId === card.decision_id}
                onRespond={(choice, extra) => void respond(card, choice, extra)}
              />
            ))}
          </div>
        )}
      </section>

      <section>
        <SectionHeading
          aside={
            <Link href="/activity" className="underline decoration-line underline-offset-4">
              Full trail
            </Link>
          }
        >
          Handled without asking
        </SectionHeading>

        {silent.loading ? (
          <div>
            <RowSkeleton />
            <RowSkeleton />
            <RowSkeleton />
          </div>
        ) : silent.error ? (
          <ErrorState error={silent.error} onRetry={() => void silent.reload()} />
        ) : handled.length === 0 ? (
          <p className="py-6 text-sm text-muted">Nothing yet today.</p>
        ) : (
          <ul>
            {handled.slice(0, 8).map((entry) => (
              <SilentRow key={entry.entry_id} entry={entry} timezone={timezone} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/**
 * The empty state. The screenshot that communicates the whole idea.
 *
 * No illustration, no "you're all caught up!" exclamation mark. The product's
 * claim is that it is quietly competent, and the empty state should sound like
 * someone reliable telling you there is nothing to worry about.
 */
function EmptyInbox() {
  return (
    <div className="rounded-card border border-line bg-surface px-6 py-14 text-center">
      <svg
        width="30"
        height="30"
        viewBox="0 0 24 24"
        fill="none"
        className="mx-auto text-calm"
        aria-hidden
      >
        <path
          d="M4 12.6 9.2 18 20 6.6"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <p className="mt-4 text-[15px] font-medium text-ink">Your inbox is empty</p>
      <p className="mx-auto mt-1.5 max-w-xs text-sm leading-relaxed text-muted">
        Quiet Hours is watching your bills, renewals and appointments. It will only appear here
        when something genuinely needs you.
      </p>
    </div>
  );
}

function SilentRow({ entry, timezone }: { entry: ActivityEntry; timezone: string }) {
  return (
    <li className="flex items-baseline gap-3 border-b border-line py-3 last:border-0">
      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-calm" aria-hidden />
      <span className="flex-1 text-sm leading-relaxed text-ink-soft">{entry.summary}</span>
      {entry.impact ? (
        <span className="tnum text-sm font-medium text-calm">{formatMoney(entry.impact)}</span>
      ) : null}
      <span className="tnum w-12 shrink-0 text-right text-xs text-muted">
        {formatTime(entry.occurred_at, timezone)}
      </span>
    </li>
  );
}
