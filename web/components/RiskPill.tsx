'use client';

/**
 * The risk tier of an action, in the user's language rather than the codebase's.
 *
 * `never_auto` reads as "always asks you" because that is what it means to the
 * person reading it — the guarantee, not the internal name.
 *
 * The switch has a default branch on purpose: Lane A can add a tier, and an
 * unknown one must render as itself rather than throw or vanish.
 */

import type { RiskTier } from '@contracts';
import { humanise } from '@/lib/format';

const LABELS: Record<RiskTier, { label: string; hint: string }> = {
  silent: { label: 'Routine', hint: 'Reversible, no outside effect. Done and logged.' },
  notify: { label: 'Low risk', hint: 'Harmless and reversible. Done, and shown in the digest.' },
  confirm: {
    label: 'Needs a rule',
    hint: 'Spends money, sends a message or changes a service. Asks unless a rule covers it.',
  },
  never_auto: {
    label: 'Always asks you',
    hint: 'Irreversible or high value. No rule can ever auto-approve it.',
  },
};

export function RiskPill({ risk }: { risk: RiskTier | string }) {
  const known = LABELS[risk as RiskTier];
  const label = known?.label ?? humanise(String(risk));
  return (
    <span
      title={known?.hint}
      className="shrink-0 rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-muted"
    >
      {label}
    </span>
  );
}
