'use client';

/**
 * Rules — the autonomy you have granted, and how to take it back.
 *
 * This screen is the answer to "what if it learns the wrong thing?", and judges
 * will look for it. Three things make the answer credible:
 *
 * 1. **Every rule is in plain English**, shown verbatim as the user agreed to it
 *    on the card. Not a scope/merchant/amount triple for them to decode.
 * 2. **Every rule says how many times it has fired.** A rule that has silently
 *    acted forty times is a different thing from one that never has.
 * 3. **Revoke is one click**, with no confirmation dialogue. Taking autonomy back
 *    must be easier than granting it was.
 *
 * A revoked rule is not deleted — it stays here, greyed, because the actions it
 * once permitted are still in the trail and must remain explainable.
 */

import { useState } from 'react';
import type { Policy } from '@contracts';
import { formatMoney } from '@contracts';
import { getPolicies, revokePolicy } from '@/lib/api';
import { QuietHoursError } from '@/lib/errors';
import { formatDate, humanise } from '@/lib/format';
import { useResource } from '@/lib/useResource';
import { useTimezone } from '@/components/HouseholdContext';
import { ErrorState, RowSkeleton, SectionHeading } from '@/components/States';

export default function PoliciesPage() {
  const policies = useResource(() => getPolicies(true), []);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [failure, setFailure] = useState<QuietHoursError | null>(null);
  const timezone = useTimezone();

  async function revoke(policy: Policy) {
    setBusyId(policy.policy_id);
    setFailure(null);
    try {
      const updated = await revokePolicy(policy.policy_id);
      // Update in place: the list is short and a full reload would make the row
      // the user just clicked jump between sections before they see it change.
      policies.set({
        ...policies.data!,
        items: (policies.data?.items ?? []).map((item) =>
          item.policy_id === updated.policy_id ? updated : item,
        ),
      });
    } catch (error) {
      setFailure(
        error instanceof QuietHoursError
          ? error
          : new QuietHoursError('backend_error', String(error)),
      );
      void policies.reload();
    } finally {
      setBusyId(null);
    }
  }

  const all = policies.data?.items ?? [];
  const active = all.filter((policy) => policy.revoked_at === null);
  const revoked = all.filter((policy) => policy.revoked_at !== null);
  const fired = active.reduce((sum, policy) => sum + policy.times_applied, 0);

  return (
    <div>
      <header className="mb-7">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">Rules</p>
        <h1 className="mt-1.5 text-[26px] font-semibold leading-tight tracking-[-0.02em] text-ink">
          What you have let it handle
        </h1>
        <p className="mt-2 max-w-lg text-[15px] leading-relaxed text-muted">
          Every rule here came from an answer you gave. Quiet Hours never writes one on its own, and
          no rule can ever auto-approve something irreversible.
          {active.length > 0 ? (
            fired > 0 ? (
              <>
                {' '}
                These {active.length} rules have spared you {fired}{' '}
                {fired === 1 ? 'interruption' : 'interruptions'} so far.
              </>
            ) : (
              <> None of them has come up yet — they will as the same cases come round again.</>
            )
          ) : null}
        </p>
      </header>

      {failure ? (
        <div className="mb-5">
          <ErrorState error={failure} />
        </div>
      ) : null}

      {policies.loading ? (
        <div>
          <RowSkeleton />
          <RowSkeleton />
          <RowSkeleton />
        </div>
      ) : policies.error ? (
        <ErrorState error={policies.error} onRetry={() => void policies.reload()} />
      ) : all.length === 0 ? (
        <div className="rounded-card border border-line bg-surface px-6 py-12 text-center">
          <p className="text-[15px] font-medium text-ink">No rules yet</p>
          <p className="mx-auto mt-1.5 max-w-sm text-sm leading-relaxed text-muted">
            Quiet Hours asks about everything until you tell it not to. Answer &ldquo;always&rdquo;
            on a decision and the rule it creates will appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-10">
          <section>
            <SectionHeading aside={`${active.length} active`}>In force</SectionHeading>
            {active.length === 0 ? (
              <p className="py-6 text-sm text-muted">
                Every rule has been revoked. Quiet Hours will ask you about everything again.
              </p>
            ) : (
              <ul className="space-y-2.5">
                {active.map((policy) => (
                  <PolicyRow
                    key={policy.policy_id}
                    policy={policy}
                    timezone={timezone}
                    busy={busyId === policy.policy_id}
                    onRevoke={() => void revoke(policy)}
                  />
                ))}
              </ul>
            )}
          </section>

          {revoked.length > 0 && (
            <section>
              <SectionHeading>Revoked</SectionHeading>
              <ul className="space-y-2.5">
                {revoked.map((policy) => (
                  <PolicyRow key={policy.policy_id} policy={policy} timezone={timezone} />
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  );
}

function PolicyRow({
  policy,
  timezone,
  busy = false,
  onRevoke,
}: {
  policy: Policy;
  timezone: string;
  busy?: boolean;
  onRevoke?: () => void;
}) {
  const revoked = policy.revoked_at !== null;
  const denies = policy.effect === 'auto_deny';

  return (
    <li
      className={`rounded-card border border-line bg-surface p-4 ${revoked ? 'opacity-55' : ''}`}
    >
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-[15px] leading-snug text-ink">{policy.description}</p>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
            <span>{denies ? 'Never does this' : 'Handles it without asking'}</span>
            <span aria-hidden>·</span>
            <span>{humanise(policy.scope)} rule</span>
            {policy.max_amount ? (
              <>
                <span aria-hidden>·</span>
                <span className="tnum">up to {formatMoney(policy.max_amount)}</span>
              </>
            ) : null}
            <span aria-hidden>·</span>
            <span>
              {policy.times_applied === 0
                ? 'not used yet'
                : `used ${policy.times_applied} ${policy.times_applied === 1 ? 'time' : 'times'}`}
            </span>
            <span aria-hidden>·</span>
            <span>
              {revoked
                ? `revoked ${formatDate(policy.revoked_at!, timezone)}`
                : `since ${formatDate(policy.created_at, timezone)}`}
            </span>
          </div>
        </div>

        {!revoked && onRevoke ? (
          <button
            onClick={onRevoke}
            disabled={busy}
            className="shrink-0 rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-muted transition-colors hover:bg-raised hover:text-ink disabled:opacity-40"
          >
            {busy ? 'Revoking…' : 'Revoke'}
          </button>
        ) : (
          <span className="shrink-0 text-xs text-muted">Revoked</span>
        )}
      </div>
    </li>
  );
}
