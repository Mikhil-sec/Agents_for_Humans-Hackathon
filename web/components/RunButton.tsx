'use client';

/**
 * "Check now" — the demo button.
 *
 * The agent normally wakes on a schedule; nobody would sit and watch it. This
 * exists so a judge with four minutes can see a run happen, and so the graph's
 * stages are legible rather than implied. It narrates over SSE and then hands
 * control back to the page to reload.
 *
 * It is not a chat input, and it takes no text.
 */

import { useEffect, useRef, useState } from 'react';
import { triggerRun } from '@/lib/api';
import { followRun } from '@/lib/stream';

export function RunButton({ onFinished }: { onFinished: () => void }) {
  const [message, setMessage] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const close = useRef<(() => void) | null>(null);

  useEffect(() => () => close.current?.(), []);

  async function start() {
    setRunning(true);
    setMessage('Waking up');
    try {
      const run = await triggerRun();
      close.current = followRun(run.run_id, {
        onProgress: (event) => setMessage(event.message),
        onFinished: () => {
          setMessage(null);
          setRunning(false);
          onFinished();
        },
        onError: (detail) => {
          setMessage(detail);
          setRunning(false);
        },
      });
    } catch {
      setMessage('Could not reach the agent');
      setRunning(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      {message ? (
        <span className="text-sm text-muted" aria-live="polite">
          {message}
          {running ? '…' : ''}
        </span>
      ) : null}
      <button
        onClick={start}
        disabled={running}
        className="rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-ink transition-colors hover:bg-raised disabled:opacity-40"
      >
        {running ? 'Checking' : 'Check now'}
      </button>
    </div>
  );
}
