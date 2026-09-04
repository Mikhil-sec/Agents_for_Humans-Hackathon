"use client";

/**
 * The decision card. The one place the agent is allowed to interrupt.
 *
 * Four things are non-negotiable here, and each of them is a product rule rather
 * than a styling preference:
 *
 * 1. **`why_asking` is always visible.** Never behind a disclosure. It is what
 *    makes the agent feel accountable rather than arbitrary — the difference
 *    between "approve this" and "I stopped because no rule of yours covers it".
 * 2. **`creates_policy_preview` is rendered prominently** on every
 *    `approve_always` / `deny_always` option. The user must never grant autonomy
 *    without reading the rule, in plain English, first.
 * 3. **Evidence is one click away**, and the click is labelled "Show me why" —
 *    the question the user is actually asking.
 * 4. **Unknown option values still render.** Lane A can add a `DecisionChoice`
 *    mid-build; an unrecognised one degrades to a plain button with its own
 *    label, and never throws.
 */

import { useEffect, useState } from "react";
import type {
  DecisionCard as Card,
  DecisionChoice,
  DecisionOption,
} from "@contracts";
import { formatMoney } from "@contracts";
import { countdownTo, formatDateTime, hasPassed } from "@/lib/format";
import { useTimezone } from "./HouseholdContext";

/** Live countdown to a deadline. */
function Countdown({ deadline }: { deadline: string }) {
  // Mounted-guarded: the value depends on `Date.now()`, which differs between
  // the server render and the client and would otherwise hydrate mismatched.
  const [remaining, setRemaining] = useState<string | null>(null);

  useEffect(() => {
    const tick = () => setRemaining(countdownTo(deadline));
    tick();
    const timer = setInterval(tick, 30_000);
    return () => clearInterval(timer);
  }, [deadline]);

  if (remaining === null) return null;
  if (remaining === "") {
    return (
      <span className="text-xs font-medium text-muted">Deadline passed</span>
    );
  }
  return (
    <span className="tnum rounded-full bg-accent-wash px-2.5 py-1 text-xs font-medium text-accent">
      {remaining} left
    </span>
  );
}

/**
 * How each choice looks.
 *
 * The default option is the visually primary one — the agent's recommendation,
 * not a colour applied to whichever button came first. Destructive-sounding
 * choices are never styled as alarming: declining is a perfectly ordinary answer
 * and should not feel like an error.
 */
function optionStyle(option: DecisionOption): string {
  const base =
    "rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  if (option.is_default) {
    return `${base} bg-accent text-accent-ink hover:opacity-90`;
  }
  switch (option.choice) {
    case "approve":
    case "approve_always":
    case "edit":
      return `${base} border border-line text-ink hover:bg-raised`;
    case "deny":
    case "deny_always":
    case "snooze":
      return `${base} text-muted hover:bg-raised hover:text-ink`;
    default:
      // An unknown choice Lane A added after this build. Render it plainly.
      return `${base} border border-line text-ink hover:bg-raised`;
  }
}

function grantsAutonomy(choice: DecisionChoice | string): boolean {
  return choice === "approve_always" || choice === "deny_always";
}

export function DecisionCard({
  card,
  onRespond,
  busy = false,
}: {
  card: Card;
  onRespond: (choice: DecisionChoice, extra?: { note?: string | null }) => void;
  busy?: boolean;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const timezone = useTimezone();

  const expired =
    card.status === "expired" ||
    (card.urgency_deadline !== null && hasPassed(card.urgency_deadline));
  const resolved = card.status === "resolved" || card.status === "withdrawn";
  const locked = expired || resolved || busy;

  const autonomyOptions = card.options.filter((o) => grantsAutonomy(o.choice));

  return (
    <article
      className="rise overflow-hidden rounded-card border border-line bg-surface"
      aria-labelledby={`headline-${card.decision_id}`}
    >
      {/* The one accent stripe in the product: this needs you. */}
      <div className={expired ? "h-1 bg-line" : "h-1 bg-accent"} aria-hidden />

      <div className="p-6">
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-accent">
            {expired ? "Expired" : resolved ? "Answered" : "Needs you"}
          </span>
          {card.urgency_deadline && !resolved ? (
            <Countdown deadline={card.urgency_deadline} />
          ) : (
            <span className="text-xs text-muted">
              {formatDateTime(card.created_at, timezone)}
            </span>
          )}
        </div>

        <h2
          id={`headline-${card.decision_id}`}
          className="text-[19px] font-semibold leading-snug tracking-[-0.01em] text-ink"
        >
          {card.headline}
        </h2>

        <p className="mt-2 text-[15px] leading-relaxed text-ink-soft">
          {card.body}
        </p>

        {(card.amount || card.estimated_impact) && (
          <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2">
            {card.amount ? (
              <div>
                <dt className="text-xs text-muted">Amount</dt>
                <dd className="tnum text-[15px] font-semibold text-ink">
                  {formatMoney(card.amount)}
                </dd>
              </div>
            ) : null}
            {card.estimated_impact ? (
              <div>
                <dt className="text-xs text-muted">If you approve</dt>
                <dd className="tnum text-[15px] font-semibold text-calm">
                  {formatMoney(card.estimated_impact)} saved
                </dd>
              </div>
            ) : null}
          </dl>
        )}

        {/* Rule 1: always visible. Never behind a disclosure. */}
        <div className="mt-5 border-l-2 border-line pl-3.5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
            Why I&rsquo;m asking
          </p>
          <p className="mt-1 text-sm leading-relaxed text-ink-soft">
            {card.why_asking}
          </p>
        </div>

        {card.evidence.length > 0 && (
          <div className="mt-4">
            <button
              onClick={() => setShowEvidence((open) => !open)}
              aria-expanded={showEvidence}
              className="text-sm font-medium text-muted underline decoration-line underline-offset-4 transition-colors hover:text-ink"
            >
              {showEvidence ? "Hide the evidence" : "Show me why"}
            </button>
            {showEvidence && (
              <ul className="mt-3 space-y-2">
                {card.evidence.map((item, index) => (
                  <li
                    key={`${item.signal_id}-${index}`}
                    className="rounded-lg bg-raised px-3.5 py-3 text-sm leading-relaxed text-ink-soft"
                  >
                    <p>{item.excerpt}</p>
                    <p className="mt-1.5 font-mono text-[11px] text-muted">
                      {item.source_ref ?? item.signal_id}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Rule 2: the rule, in plain English, before the button that grants it. */}
        {autonomyOptions.length > 0 && !locked && (
          <div className="mt-5 rounded-lg border border-line bg-raised p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
              Answering &ldquo;always&rdquo; creates a rule
            </p>
            <ul className="mt-2 space-y-1.5">
              {autonomyOptions.map((option) => (
                <li
                  key={option.choice}
                  className="text-sm leading-relaxed text-ink"
                >
                  <span className="text-muted">{option.label}:</span>{" "}
                  {option.creates_policy_preview ??
                    "a rule covering cases like this one"}
                </li>
              ))}
            </ul>
            <p className="mt-2.5 text-xs text-muted">
              You can revoke any rule from the Rules page. Quiet Hours will
              never write one you have not read.
            </p>
          </div>
        )}

        {editing && (
          <div className="mt-5">
            <label
              htmlFor={`note-${card.decision_id}`}
              className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted"
            >
              What should it do instead?
            </label>
            <textarea
              id={`note-${card.decision_id}`}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              className="mt-2 w-full rounded-lg border border-line bg-canvas p-3 text-sm text-ink outline-none focus:border-accent"
              placeholder="e.g. pay it, but on the 28th rather than today"
            />
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => onRespond("edit", { note: note.trim() || null })}
                disabled={busy}
                className="rounded-lg bg-accent px-3.5 py-2 text-sm font-medium text-accent-ink hover:opacity-90 disabled:opacity-40"
              >
                Send that back
              </button>
              <button
                onClick={() => setEditing(false)}
                className="rounded-lg px-3.5 py-2 text-sm font-medium text-muted hover:text-ink"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {!locked && !editing && (
          <div className="mt-6 flex flex-wrap items-center gap-2">
            {card.options.map((option) => (
              <button
                key={option.choice}
                onClick={() =>
                  option.choice === "edit"
                    ? setEditing(true)
                    : onRespond(option.choice)
                }
                disabled={busy}
                title={option.description ?? undefined}
                className={optionStyle(option)}
              >
                {option.label}
              </button>
            ))}
            {busy ? <span className="text-sm text-muted">Saving…</span> : null}
          </div>
        )}

        {expired && !resolved && (
          <p className="mt-6 rounded-lg bg-raised px-3.5 py-3 text-sm text-muted">
            This one timed out before it was answered, so Quiet Hours did
            nothing. It is in your activity trail with the reasoning.
          </p>
        )}

        {/* Sub-labels for the plain options. The `*_always` ones are deliberately
            excluded: the rule box above already explains them, and saying it
            twice makes the card look like it is arguing for the answer. */}
        {card.options.some((o) => o.description && !grantsAutonomy(o.choice)) &&
          !locked &&
          !editing && (
            <ul className="mt-4 space-y-1">
              {card.options
                .filter((o) => o.description && !grantsAutonomy(o.choice))
                .map((option) => (
                  <li
                    key={`desc-${option.choice}`}
                    className="text-xs leading-relaxed text-muted"
                  >
                    <span className="text-ink-soft">{option.label}</span> —{" "}
                    {option.description}
                  </li>
                ))}
            </ul>
          )}
      </div>
    </article>
  );
}
