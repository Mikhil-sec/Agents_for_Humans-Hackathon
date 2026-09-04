'use client';

/**
 * The household, fetched once and shared.
 *
 * Its only job on most screens is `timezone`. Timestamps arrive as UTC and are
 * converted here at render time — never earlier, never stored converted. Until
 * the household loads we fall back to the contract's own default rather than to
 * the browser's zone, so a page never briefly renders times in a zone the user
 * does not live in and then silently changes them.
 */

import { createContext, useContext } from 'react';
import type { Household } from '@contracts';
import { DEFAULT_TIMEZONE } from '@/lib/format';

export const HouseholdContext = createContext<Household | null>(null);

export const useHousehold = () => useContext(HouseholdContext);

export function useTimezone(): string {
  return useContext(HouseholdContext)?.timezone ?? DEFAULT_TIMEZONE;
}
