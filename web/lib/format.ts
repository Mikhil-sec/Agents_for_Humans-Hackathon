/**
 * Formatting.
 *
 * Two lane rules live here:
 *
 * 1. **Money goes through `formatMoney()` from the contracts.** `amount_minor`
 *    is an integer count of minor units. Nothing in `/web` divides by 100, and
 *    nothing does arithmetic on a formatted string.
 * 2. **Timestamps are UTC on the wire** and are converted to the household's
 *    timezone at render time only — never on the way in, never stored converted.
 */

import type { IsoDateTime, Money } from '@contracts';
import { formatMoney } from '@contracts';

export { formatMoney };

export const DEFAULT_TIMEZONE = 'Europe/London';

/** Sum a list of `Money` in minor units. The one safe way to add money here. */
export function totalMinor(amounts: (Money | null | undefined)[]): Money | null {
  const present = amounts.filter((m): m is Money => !!m);
  if (present.length === 0) return null;
  return {
    amount_minor: present.reduce((sum, m) => sum + m.amount_minor, 0),
    currency: present[0].currency,
  };
}

function zoned(iso: IsoDateTime, timezone: string, options: Intl.DateTimeFormatOptions): string {
  try {
    return new Intl.DateTimeFormat('en-GB', { ...options, timeZone: timezone }).format(
      new Date(iso),
    );
  } catch {
    // An unknown IANA zone from the API must not blank the screen.
    return new Intl.DateTimeFormat('en-GB', options).format(new Date(iso));
  }
}

export const formatTime = (iso: IsoDateTime, tz = DEFAULT_TIMEZONE) =>
  zoned(iso, tz, { hour: '2-digit', minute: '2-digit' });

export const formatDate = (iso: IsoDateTime, tz = DEFAULT_TIMEZONE) =>
  zoned(iso, tz, { day: 'numeric', month: 'short' });

export const formatDateTime = (iso: IsoDateTime, tz = DEFAULT_TIMEZONE) =>
  zoned(iso, tz, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

export const formatDayHeading = (iso: IsoDateTime, tz = DEFAULT_TIMEZONE) =>
  zoned(iso, tz, { weekday: 'long', day: 'numeric', month: 'long' });

/** `2 days ago`, `just now`. Used where the exact minute does not matter. */
export function formatRelative(iso: IsoDateTime, now: Date = new Date()): string {
  const seconds = Math.round((new Date(iso).getTime() - now.getTime()) / 1000);
  const absolute = Math.abs(seconds);
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['second', 60],
    ['minute', 3600],
    ['hour', 86400],
    ['day', 604800],
    ['week', 2629800],
    ['month', 31557600],
  ];
  const formatter = new Intl.RelativeTimeFormat('en-GB', { numeric: 'auto' });
  if (absolute < 45) return 'just now';
  let previous = 1;
  for (const [unit, limit] of units) {
    if (absolute < limit) return formatter.format(Math.round(seconds / previous), unit);
    previous = limit;
  }
  return formatter.format(Math.round(seconds / 31557600), 'year');
}

/** How long until a deadline, as `4h 12m`. Empty once it has passed. */
export function countdownTo(iso: IsoDateTime, now: Date = new Date()): string {
  const ms = new Date(iso).getTime() - now.getTime();
  if (ms <= 0) return '';
  const minutes = Math.floor(ms / 60000);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  return `${minutes}m`;
}

export const hasPassed = (iso: IsoDateTime, now: Date = new Date()) =>
  new Date(iso).getTime() <= now.getTime();

/** `86%`. The autonomy rate is a 0..1 float on the wire. */
export const formatPercent = (rate: number) => `${Math.round(rate * 100)}%`;

/**
 * Turn an enum value into something readable, for the cases where the UI has no
 * copy of its own — an unknown `FindingKind` or `ActionKind` added by Lane A
 * mid-build lands here rather than rendering as a raw token or throwing.
 */
export const humanise = (value: string) =>
  value.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
