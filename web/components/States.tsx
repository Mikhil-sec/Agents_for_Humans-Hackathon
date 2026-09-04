'use client';

/**
 * Loading, error and section-empty states.
 *
 * These are the states that make a product feel finished or unfinished, and in
 * this one they carry unusual weight: an empty inbox is *success*, so "empty"
 * and "broken" and "not loaded yet" must be impossible to confuse. Each of the
 * three looks distinctly different on purpose.
 */

import type { QuietHoursError } from '@/lib/errors';
import { explain } from '@/lib/errors';

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`pulse rounded-lg bg-line ${className}`} aria-hidden />;
}

export function CardSkeleton() {
  return (
    <div className="rounded-card border border-line bg-surface p-6" aria-busy>
      <span className="sr-only">Loading</span>
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-4 h-5 w-2/3" />
      <Skeleton className="mt-3 h-4 w-full" />
      <Skeleton className="mt-2 h-4 w-4/5" />
      <div className="mt-6 flex gap-2">
        <Skeleton className="h-9 w-28" />
        <Skeleton className="h-9 w-32" />
      </div>
    </div>
  );
}

export function RowSkeleton() {
  return (
    <div className="flex items-center gap-3 border-b border-line py-3.5" aria-busy>
      <Skeleton className="h-4 w-4 rounded-full" />
      <Skeleton className="h-4 flex-1" />
      <Skeleton className="h-3 w-14" />
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: QuietHoursError;
  onRetry?: () => void;
}) {
  const { title, detail } = explain(error);
  return (
    <div
      role="alert"
      className="rounded-card border border-line bg-surface px-6 py-8 text-center"
    >
      <p className="text-[15px] font-medium text-ink">{title}</p>
      <p className="mx-auto mt-1.5 max-w-sm text-sm leading-relaxed text-muted">{detail}</p>
      {onRetry ? (
        <button
          onClick={onRetry}
          className="mt-5 rounded-lg border border-line px-3.5 py-1.5 text-sm font-medium text-ink transition-colors hover:bg-raised"
        >
          Try again
        </button>
      ) : null}
      <p className="mt-4 font-mono text-[11px] text-muted">{error.code}</p>
    </div>
  );
}

/** For a section that is legitimately empty — not an error, not still loading. */
export function SectionEmpty({ children }: { children: React.ReactNode }) {
  return <p className="py-8 text-center text-sm text-muted">{children}</p>;
}

export function SectionHeading({
  children,
  aside,
}: {
  children: React.ReactNode;
  aside?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-4">
      <h2 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
        {children}
      </h2>
      {aside ? <span className="text-xs text-muted">{aside}</span> : null}
    </div>
  );
}
