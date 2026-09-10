'use client';

/**
 * Loading a resource, with every state the product actually has.
 *
 * `loading`, `error` and `offline` are not afterthoughts here: this is a screen
 * that is *usually empty*, so "empty" and "broken" must never look alike. A
 * spinner that silently becomes nothing would read as "nothing needs you" — the
 * one wrong message this product can send.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { QuietHoursError } from './errors';

export interface Resource<T> {
  data: T | null;
  error: QuietHoursError | null;
  /** True only on the first load. A refresh keeps the current data on screen. */
  loading: boolean;
  refreshing: boolean;
  reload: () => Promise<void>;
  /** Update in place after a write, without a round trip. */
  set: (next: T) => void;
}

export function useResource<T>(load: () => Promise<T>, deps: unknown[] = []): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<QuietHoursError | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const mounted = useRef(true);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(async (first: boolean) => {
    if (first) setLoading(true);
    else setRefreshing(true);
    try {
      const next = await loadRef.current();
      if (!mounted.current) return;
      setData(next);
      setError(null);
    } catch (caught) {
      if (!mounted.current) return;
      setError(
        caught instanceof QuietHoursError
          ? caught
          : new QuietHoursError('backend_error', String(caught)),
      );
    } finally {
      if (mounted.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    void run(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  // Coming back from offline or from a background tab should refill the screen
  // without the user having to think about reloading.
  useEffect(() => {
    const refresh = () => void run(false);
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh();
    };
    window.addEventListener('online', refresh);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.removeEventListener('online', refresh);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [run]);

  return {
    data,
    error,
    loading,
    refreshing,
    reload: () => run(false),
    set: setData,
  };
}

/** Whether the browser currently believes it is online. */
export function useOnline(): boolean {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    update();
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  }, []);
  return online;
}
