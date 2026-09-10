/**
 * The typed API client.
 *
 * Every payload type on this seam comes from `contracts/typescript/index.ts`.
 * Nothing here redeclares an API shape, and there is no `any`: if a response
 * does not match the contract, that is a bug in the API or a stale deploy, and
 * the contract-version banner is what catches it.
 *
 * The wire format is snake_case all the way to the component. It is not mapped
 * to camelCase anywhere — see `AGENTS.md`, "Naming".
 */

import type {
  ActivityEntry,
  DailyBrief,
  DecisionCard,
  DecisionChoice,
  DecisionResponse,
  Household,
  Page,
  Policy,
  Run,
} from '@contracts';
import { CONTRACT_VERSION } from '@contracts';
import { QuietHoursError } from './errors';

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000').replace(
  /\/$/,
  '',
);

/** The version the API last answered with. Read by the mismatch banner. */
let observedContractVersion: string | null = null;

export function serverContractVersion(): string | null {
  return observedContractVersion;
}

/**
 * A mismatch worth interrupting the user about is a *major* one.
 *
 * A minor or patch difference means someone added a field, which every consumer
 * here tolerates. A major difference means a shape changed underneath a deploy,
 * and the screen may be showing wrong data — which in this product is the one
 * failure the user cannot detect on their own, because a quiet screen is what
 * success looks like.
 */
export function isMajorMismatch(server: string | null): boolean {
  if (!server) return false;
  return server.split('.')[0] !== CONTRACT_VERSION.split('.')[0];
}

interface ApiErrorBody {
  error?: string;
  message?: string;
  contract_version?: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      cache: 'no-store',
    });
  } catch {
    // fetch only rejects when the request never completed: no network, DNS
    // failure, the API not running. Everything else is a status code.
    throw new QuietHoursError('offline', 'could not reach the Quiet Hours API');
  }

  const header = response.headers.get('X-Contract-Version');
  if (header) observedContractVersion = header;

  if (!response.ok) {
    let body: ApiErrorBody = {};
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // A non-JSON error body (a proxy's HTML 502, say). The status is all we have.
    }
    if (body.contract_version) observedContractVersion = body.contract_version;
    throw new QuietHoursError(
      body.error ?? 'backend_error',
      body.message ?? `${response.status} ${response.statusText}`,
      response.status,
    );
  }

  const body = (await response.json()) as T & { contract_version?: string };
  if (body && typeof body === 'object' && body.contract_version) {
    observedContractVersion = body.contract_version;
  }
  return body;
}

// -- reads ------------------------------------------------------------------

export const getHousehold = () => request<Household>('/api/household');

export const getPendingDecisions = () =>
  request<Page<DecisionCard>>('/api/decisions?status=pending');

export const getAllDecisions = () => request<Page<DecisionCard>>('/api/decisions?status=all');

export const getDecision = (id: string) => request<DecisionCard>(`/api/decisions/${id}`);

export const getRuns = () => request<Page<Run>>('/api/runs');

export const getActivity = (autonomous?: boolean) =>
  request<Page<ActivityEntry>>(
    `/api/activity${autonomous === undefined ? '' : `?autonomous=${autonomous}`}`,
  );

export const getPolicies = (includeRevoked = false) =>
  request<Page<Policy>>(`/api/policies?include_revoked=${includeRevoked}`);

export const getBrief = () => request<DailyBrief>('/api/brief/latest');

export const getHealth = () =>
  request<{ status: string; backend: string; contract_version: string }>('/api/health');

// -- writes -----------------------------------------------------------------

/** What `POST /api/decisions/{id}/respond` answers with. */
export interface RespondResult {
  run_id: string;
  status: string;
  decision_id: string;
  choice: DecisionChoice;
  contract_version: string;
}

/**
 * Answer a decision card.
 *
 * The card's `session_id`, `interrupt_id` and `interrupt_name` are **opaque**:
 * they are not touched here, and they are not sent here either — the API reads
 * them off the stored card. This function sends only what the contract's
 * `DecisionResponse` describes.
 */
export function respondToDecision(
  decisionId: string,
  choice: DecisionChoice,
  extra: Partial<Pick<DecisionResponse, 'edited_params' | 'snooze_until' | 'note'>> = {},
): Promise<RespondResult> {
  const body: DecisionResponse = {
    decision_id: decisionId,
    choice,
    edited_params: extra.edited_params ?? null,
    snooze_until: extra.snooze_until ?? null,
    note: extra.note ?? null,
    responded_at: new Date().toISOString(),
  };
  return request<RespondResult>(`/api/decisions/${decisionId}/respond`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export const revokePolicy = (id: string) =>
  request<Policy>(`/api/policies/${id}`, { method: 'DELETE' });

export const triggerRun = () => request<Run>('/api/runs', { method: 'POST' });
