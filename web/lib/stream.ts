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
import { API_BASE } from './api';

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
