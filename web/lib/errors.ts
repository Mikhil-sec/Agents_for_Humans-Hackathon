/**
 * The API's stable error codes.
 *
 * Mirrors `api/app/errors.py`. These are a contract between two files in the
 * same lane: the API promises never to change a code without changing this list
 * in the same PR, and the UI switches on them rather than on HTTP status or,
 * worse, on the wording of a message.
 */

export const ERROR_CODES = [
  'decision_not_found',
  'decision_not_pending',
  'run_not_found',
  'policy_not_found',
  'brief_not_found',
  'fixtures_missing',
  'invalid_request',
  'invalid_choice',
  'agent_unavailable',
  'backend_error',
  // Client-side only. The network never reached the API.
  'offline',
] as const;

export type ErrorCode = (typeof ERROR_CODES)[number];

export class QuietHoursError extends Error {
  readonly code: ErrorCode | string;
  readonly status: number;

  constructor(code: ErrorCode | string, message: string, status = 0) {
    super(message);
    this.name = 'QuietHoursError';
    this.code = code;
    this.status = status;
  }
}

/**
 * What to put on screen for each failure.
 *
 * Every branch names the thing the user can actually do next. An error screen
 * that says "something went wrong" in a product that manages someone's money is
 * worse than no error screen at all.
 *
 * Unknown codes fall through to the default deliberately: the API may add a code
 * mid-build, and an unrecognised one must degrade to a sentence, never throw.
 */
export function explain(error: QuietHoursError): { title: string; detail: string } {
  switch (error.code) {
    case 'offline':
      return {
        title: "You're offline",
        detail:
          'Quiet Hours keeps working while you are away — nothing is lost. This page will fill in when the connection is back.',
      };
    case 'fixtures_missing':
      return {
        title: 'No data to show yet',
        detail: 'Run `make fixtures` from the repo root, then reload this page.',
      };
    case 'decision_not_found':
      return {
        title: 'That decision is gone',
        detail: 'It was answered or withdrawn. Your activity trail has the record.',
      };
    case 'decision_not_pending':
      return {
        title: 'Already answered',
        detail: 'Someone answered this from another device. Nothing was done twice.',
      };
    case 'agent_unavailable':
      return {
        title: 'The agent is not reachable',
        detail:
          'Your answer was saved and the run will pick it up when the agent is back. Nothing was lost.',
      };
    case 'brief_not_found':
      return {
        title: 'No brief yet',
        detail: 'The agent has not finished a run for today.',
      };
    default:
      return {
        title: 'That did not load',
        detail: error.message || 'Try again in a moment.',
      };
  }
}
