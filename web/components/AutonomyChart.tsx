'use client';

/**
 * The autonomy chart — the demo's headline visual.
 *
 * Two lines over the weeks the agent has been running: decisions raised, which
 * falls, and actions handled silently, which rises. The crossing of those two
 * lines is the entire product thesis in one picture, so the chart's job is to
 * make the *trend* legible, not to be admired.
 *
 * Deliberate choices, in the order they were made:
 *
 * - **One axis.** Both series are counts of actions in the same run, so they
 *   share a scale honestly. Money is a different unit and lives in a stat tile
 *   beside the chart rather than on a second y-axis.
 * - **Colour follows meaning, not slot order.** Warm is "this needed you" —
 *   the same meaning the accent carries everywhere else in the product. Aqua is
 *   "handled without asking". A reader who has used the app already knows what
 *   the colours mean before reading the legend.
 * - **The palette is validated, not eyeballed.** Both pairs pass the six checks
 *   (lightness band, chroma floor, CVD separation, normal-vision floor, contrast
 *   against the surface) in their own mode. Dark is its own pair of steps, not a
 *   flip of the light one.
 * - **Identity is never colour alone**: both series are directly labelled at
 *   their last point, the legend is always present, and a table view carries the
 *   same numbers for anyone the colours fail.
 */

import { useState } from 'react';
import type { Run } from '@contracts';
import { autonomyRate } from '@contracts';
import { formatDate, formatPercent } from '@/lib/format';

export interface WeekPoint {
  label: string;
  raised: number;
  silent: number;
  rate: number;
}

/**
 * One point per run, oldest first.
 *
 * A resumed run reports zero signals and findings by design — the graph replays
 * only the interrupted node — so runs that proposed nothing are dropped rather
 * than plotted as a dip the agent did not actually have.
 */
export function weeksFromRuns(runs: Run[], timezone: string): WeekPoint[] {
  return runs
    .filter((run) => run.stats.actions_proposed > 0)
    .slice()
    .sort((a, b) => a.started_at.localeCompare(b.started_at))
    .map((run) => ({
      label: formatDate(run.started_at, timezone),
      raised: run.stats.decisions_raised,
      silent: run.stats.actions_autonomous,
      rate: autonomyRate(run.stats),
    }));
}

const VIEW_W = 720;
const VIEW_H = 264;
const PAD = { top: 20, right: 104, bottom: 34, left: 34 };

const SERIES = [
  { id: 'raised', label: 'Decisions raised', className: 'text-[var(--series-raised)]' },
  { id: 'silent', label: 'Handled silently', className: 'text-[var(--series-silent)]' },
] as const;

/**
 * A "nice" y scale: a round step, at most four intervals, and a ceiling on a
 * step boundary.
 *
 * Fractions of the data maximum produce uneven gridlines (0, 1, 3, 4, 5 for a
 * maximum of 5), which makes a reader estimate rather than read.
 */
function scale(weeks: WeekPoint[]): { ceiling: number; ticks: number[] } {
  const peak = Math.max(1, ...weeks.map((w) => Math.max(w.raised, w.silent)));
  const step = [1, 2, 5, 10, 20, 25, 50, 100].find((candidate) => peak / candidate <= 4) ?? 200;
  const ceiling = step * Math.ceil(peak / step);
  const ticks = Array.from({ length: ceiling / step + 1 }, (_, index) => index * step);
  return { ceiling, ticks };
}

export function AutonomyChart({ weeks }: { weeks: WeekPoint[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const [table, setTable] = useState(false);

  if (weeks.length === 0) {
    return (
      <p className="rounded-card border border-line bg-surface px-6 py-12 text-center text-sm text-muted">
        The agent has not completed a run yet. The trend appears here after the first one.
      </p>
    );
  }

  const { ceiling, ticks } = scale(weeks);
  const plotW = VIEW_W - PAD.left - PAD.right;
  const plotH = VIEW_H - PAD.top - PAD.bottom;

  const x = (index: number) =>
    PAD.left + (weeks.length === 1 ? plotW / 2 : (index / (weeks.length - 1)) * plotW);
  const y = (value: number) => PAD.top + plotH - (value / ceiling) * plotH;

  const path = (key: 'raised' | 'silent') =>
    weeks.map((week, index) => `${index === 0 ? 'M' : 'L'}${x(index)} ${y(week[key])}`).join(' ');

  const first = weeks[0];
  const last = weeks[weeks.length - 1];

  function locate(event: React.PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const viewX = ((event.clientX - rect.left) / rect.width) * VIEW_W;
    const step = weeks.length === 1 ? plotW : plotW / (weeks.length - 1);
    const index = Math.round((viewX - PAD.left) / step);
    setHover(Math.max(0, Math.min(weeks.length - 1, index)));
  }

  const active = hover === null ? null : weeks[hover];

  return (
    <figure className="rounded-card border border-line bg-surface p-5">
      <figcaption className="mb-1">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-[15px] font-semibold text-ink">Interruptions over time</h2>
          <button
            onClick={() => setTable((value) => !value)}
            className="shrink-0 rounded-lg border border-line px-2.5 py-1 text-xs font-medium text-muted transition-colors hover:bg-raised hover:text-ink"
          >
            {table ? 'Show chart' : 'Show numbers'}
          </button>
        </div>
        <p className="mt-1 max-w-xl text-sm leading-relaxed text-muted">
            {weeks.length > 1 ? (
              <>
                {first.raised} decisions in the first week, {last.raised} in the last. Quiet Hours
                did not get quieter on its own — every rule came from an answer you gave.
              </>
            ) : (
              'One run so far. The trend appears as the weeks accumulate.'
            )}
          </p>
      </figcaption>

      {/* Legend. Always present for two series - identity is never colour alone. */}
      <div className="mb-2 mt-3 flex flex-wrap gap-x-5 gap-y-1">
        {SERIES.map((series) => (
          <span key={series.id} className="flex items-center gap-2 text-xs text-ink-soft">
            <span
              className={`h-0.5 w-4 rounded-full bg-current ${series.className}`}
              aria-hidden
            />
            {series.label}
          </span>
        ))}
      </div>

      {table ? (
        <ChartTable weeks={weeks} />
      ) : (
        // The viewBox is 720 wide. Left to scale freely it shrinks to the
        // container, which on a 390px phone renders the 11px axis labels at
        // about 5px - the headline visual, illegible. A min-width plus
        // horizontal scroll keeps it readable and costs nothing on desktop,
        // where the container is wider than the minimum.
        <div className="relative -mx-1 overflow-x-auto px-1">
          <svg
            viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
            className="h-auto w-full min-w-[600px]"
            role="img"
            aria-label={`Decisions raised fell from ${first.raised} to ${last.raised} while actions handled silently went from ${first.silent} to ${last.silent}.`}
            onPointerMove={locate}
            onPointerLeave={() => setHover(null)}
          >
            {ticks.map((tick) => (
              <g key={tick}>
                <line
                  x1={PAD.left}
                  x2={VIEW_W - PAD.right}
                  y1={y(tick)}
                  y2={y(tick)}
                  stroke="var(--line)"
                  strokeWidth="1"
                />
                <text
                  x={PAD.left - 8}
                  y={y(tick) + 4}
                  textAnchor="end"
                  fontSize="11"
                  fill="var(--muted)"
                  className="tnum"
                >
                  {tick}
                </text>
              </g>
            ))}

            {weeks.map((week, index) => (
              <text
                key={week.label}
                x={x(index)}
                y={VIEW_H - 12}
                textAnchor="middle"
                fontSize="11"
                fill="var(--muted)"
              >
                {week.label}
              </text>
            ))}

            {active !== null && hover !== null && (
              <line
                x1={x(hover)}
                x2={x(hover)}
                y1={PAD.top}
                y2={PAD.top + plotH}
                stroke="var(--line)"
                strokeWidth="1.5"
              />
            )}

            <path
              d={path('silent')}
              fill="none"
              stroke="var(--series-silent)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d={path('raised')}
              fill="none"
              stroke="var(--series-raised)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {weeks.map((week, index) => (
              <g key={`marks-${week.label}`}>
                {/* A 2px surface ring keeps the two markers legible where the
                    lines cross - the one moment the chart most needs to be read. */}
                <circle
                  cx={x(index)}
                  cy={y(week.silent)}
                  r="4.5"
                  fill="var(--series-silent)"
                  stroke="var(--surface)"
                  strokeWidth="2"
                />
                <circle
                  cx={x(index)}
                  cy={y(week.raised)}
                  r="4.5"
                  fill="var(--series-raised)"
                  stroke="var(--surface)"
                  strokeWidth="2"
                />
              </g>
            ))}

            {/* Direct labels on the last point only. A number on every point is
                a table pretending to be a chart. */}
            <text
              x={x(weeks.length - 1) + 12}
              y={y(last.silent) + 4}
              fontSize="12"
              fontWeight="600"
              fill="var(--series-silent)"
            >
              {last.silent} silent
            </text>
            <text
              x={x(weeks.length - 1) + 12}
              y={y(last.raised) + 4}
              fontSize="12"
              fontWeight="600"
              fill="var(--series-raised)"
            >
              {last.raised} asked
            </text>
          </svg>

          {active !== null && hover !== null && (
            <div
              className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-sm"
              style={{ left: `${(x(hover) / VIEW_W) * 100}%` }}
            >
              <p className="font-medium text-ink">{active.label}</p>
              <p className="tnum mt-1 text-[var(--series-raised)]">
                {active.raised} needed you
              </p>
              <p className="tnum text-[var(--series-silent)]">{active.silent} handled silently</p>
              <p className="tnum mt-1 text-muted">{formatPercent(active.rate)} autonomous</p>
            </div>
          )}
        </div>
      )}
    </figure>
  );
}

function ChartTable({ weeks }: { weeks: WeekPoint[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th scope="col" className="py-2 font-medium">
              Week
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Needed you
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Handled silently
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              Autonomous
            </th>
          </tr>
        </thead>
        <tbody className="tnum">
          {weeks.map((week) => (
            <tr key={week.label} className="border-b border-line last:border-0">
              <td className="py-2 text-ink">{week.label}</td>
              <td className="py-2 text-right text-ink-soft">{week.raised}</td>
              <td className="py-2 text-right text-ink-soft">{week.silent}</td>
              <td className="py-2 text-right text-ink-soft">{formatPercent(week.rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
