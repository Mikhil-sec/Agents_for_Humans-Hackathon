/**
 * The live run stream (`GET /api/runs/{id}/stream`).
 *
 * These types are transport-only and are the one shape in `/web` that does not
 * come from `/contracts` — by design. `/contracts` describes *stored state*, and
 * nothing persists a progress frame. Where the stream needs to carry stored
 * state it carries the contract model whole (`run`, `pending_decisions`) rather
 * than a paraphrase of it. Mirrors `api/app/routes/runs.py`.
 */

import type { DecisionCard, Run } from '@contracts';
import { API_BASE, STATIC_MODE } from './api';

export interface RunProgressEvent {
  run_id: string;
  node: string;
  message: string;
  step: number;
  of: number;
}

export interface RunFinishedEvent {
  run_id: string;
  run: Run;
  pending_decisions: DecisionCard[];
}

export interface RunStreamHandlers {
  onProgress?: (event: RunProgressEvent) => void;
  onFinished?: (event: RunFinishedEvent, waiting: boolean) => void;
  onError?: (message: string) => void;
}

/**
 * Follow one run. Returns a function that closes the stream.
 *
 * `EventSource` reconnects on its own by default, which for a stream that ends
 * deliberately means it would restart the run narration forever — so the source
 * is closed as soon as a terminal frame arrives.
 */
export function followRun(runId: string, handlers: RunStreamHandlers): () => void {
  if (STATIC_MODE) return replayRun(runId, handlers);

  const source = new EventSource(`${API_BASE}/api/runs/${runId}/stream`);

  const finish = (waiting: boolean) => (event: MessageEvent<string>) => {
    handlers.onFinished?.(JSON.parse(event.data) as RunFinishedEvent, waiting);
    source.close();
  };

  source.addEventListener('run.progress', (event) => {
    handlers.onProgress?.(JSON.parse((event as MessageEvent<string>).data) as RunProgressEvent);
  });
  source.addEventListener('run.completed', finish(false) as EventListener);
  source.addEventListener('run.waiting', finish(true) as EventListener);
  source.addEventListener('error', (event) => {
    const data = (event as MessageEvent<string>).data;
    if (data) {
      // An error frame the API sent deliberately: it has a body and a code.
      handlers.onError?.((JSON.parse(data) as { message?: string }).message ?? 'run failed');
      source.close();
      return;
    }
    // A transport error. EventSource will retry on its own; say nothing.
  });

  return () => source.close();
}


// ---------------------------------------------------------------------------
// The hosted demo
// ---------------------------------------------------------------------------

/**
 * The five nodes the run narrates. **Mirrors `GRAPH_NODES` in
 * `api/app/routes/runs.py`, which mirrors `docs/ARCHITECTURE.md`.**
 *
 * Duplicated rather than imported because the API is Python and this build has
 * no server to ask. If the pipeline changes, both lists change — the same
 * standing arrangement `RunProgressEvent` above already has with that module.
 */
const GRAPH_NODES: ReadonlyArray<readonly [string, string]> = [
  ['ingest', 'Reading email, transactions and calendar'],
  ['triage', 'Sorting what matters from what does not'],
  ['analysis', 'Checking bills, renewals and price changes'],
  ['policy', 'Applying the rules you have already granted'],
  ['brief', 'Writing the daily brief'],
];

/** `STEP_SECONDS` in `api/app/routes/runs.py`, in milliseconds. */
const STEP_MS = 600;

/**
 * Replay the run narration with no server.
 *
 * The frames, their order, their wording and their cadence are the ones the real
 * SSE endpoint sends, so a judge watching the hosted demo sees the agentic loop
 * announce itself exactly as it does under `make demo`. What it is *not* is an
 * agent: no model is called and nothing is decided here. The run it narrates was
 * already created by `triggerRun`, and the page says the hosted demo is a
 * simulation rather than leaving that to be inferred.
 *
 * Returns the same unsubscribe function as the live path, and honours it — a
 * component that unmounts mid-narration must not keep firing handlers into a
 * dead tree.
 */
function replayRun(runId: string, handlers: RunStreamHandlers): () => void {
  let cancelled = false;
  const timers: ReturnType<typeof setTimeout>[] = [];

  const at = (delay: number, fn: () => void) => {
    timers.push(
      setTimeout(() => {
        if (!cancelled) fn();
      }, delay),
    );
  };

  GRAPH_NODES.forEach(([node, message], index) => {
    at(index * STEP_MS, () => {
      handlers.onProgress?.({
        run_id: runId,
        node,
        message,
        step: index + 1,
        of: GRAPH_NODES.length,
      });
    });
  });

  at(GRAPH_NODES.length * STEP_MS, () => {
    void (async () => {
      const { staticGetRun, staticPendingFor } = await import('./staticBackend');
      if (cancelled) return;
      const run = staticGetRun(runId);
      if (!run) {
        handlers.onError?.(`no run ${runId}`);
        return;
      }
      const pending = staticPendingFor(runId);
      handlers.onFinished?.(
        { run_id: runId, run, pending_decisions: pending },
        run.status === 'waiting_on_user',
      );
    })();
  });

  return () => {
    cancelled = true;
    timers.forEach(clearTimeout);
  };
}
