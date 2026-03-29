// =============================================================================
// CryptoQuant Engine - Custom React Hooks
// =============================================================================

import { useState, useEffect, useRef, useCallback } from "react";
import { wsManager, type WsEventType, type EventCallback } from "@/lib/websocket";

// ---------------------------------------------------------------------------
// useApi – one-shot data fetching
// ---------------------------------------------------------------------------

export interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Fetches data once (and whenever deps change). Provides refetch for manual refresh.
 *
 * @param fetcher  Async function that returns the data.
 * @param deps     Dependency array – refetches when any value changes.
 *
 * @example
 * const { data: signals, loading, error, refetch } = useApi(() => fetchSignals({ status: "active" }), []);
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: ReadonlyArray<unknown> = [],
): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Keep a ref to the latest fetcher so the memoised `load` always calls
  // the current version without needing `fetcher` in the dep array.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  // Track the mounted state to avoid setting state after unmount.
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);

    fetcherRef
      .current()
      .then((result) => {
        if (mountedRef.current) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (mountedRef.current) {
          const message = err instanceof Error ? err.message : "Unknown error";
          setError(message);
          setLoading(false);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, refetch: load };
}

// ---------------------------------------------------------------------------
// usePolling – periodic data fetching
// ---------------------------------------------------------------------------

/**
 * Like `useApi` but also re-fetches on a fixed interval.
 *
 * @param fetcher      Async function that returns the data.
 * @param intervalMs   Polling interval in milliseconds.
 * @param deps         Dependency array.
 *
 * @example
 * const { data: status } = usePolling(() => fetchBotStatus(), 5_000, []);
 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  deps: ReadonlyArray<unknown> = [],
): UseApiResult<T> {
  const result = useApi<T>(fetcher, deps);

  useEffect(() => {
    if (intervalMs <= 0) return;

    const id = setInterval(() => {
      result.refetch();
    }, intervalMs);

    return () => clearInterval(id);
    // We intentionally only depend on intervalMs here. `result.refetch` is
    // stable across renders because it is memoised inside useApi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs]);

  return result;
}

// ---------------------------------------------------------------------------
// useWebSocket – subscribe to WS events with auto-cleanup
// ---------------------------------------------------------------------------

/**
 * Subscribe to a WebSocket event. The subscription is created on mount
 * (or when deps change) and cleaned up on unmount.
 *
 * Automatically calls `wsManager.connect()` to ensure the connection is open.
 *
 * @param event     The WS event type to listen to.
 * @param callback  Handler invoked with the event's typed data.
 *
 * @example
 * useWebSocket("price_update", (data) => {
 *   // data is typed as PriceUpdate
 *   console.log(data.symbol, data.price);
 * });
 */
export function useWebSocket<T extends WsEventType>(
  event: T,
  callback: EventCallback<T>,
): void {
  // Keep a stable reference to the latest callback to avoid re-subscribing
  // every render while still calling the most recent closure.
  const callbackRef = useRef<EventCallback<T>>(callback);
  callbackRef.current = callback;

  useEffect(() => {
    // Ensure the WebSocket is connected.
    wsManager.connect();

    // The wrapper delegates to the ref so the latest closure is always called
    // without needing to re-subscribe on every render.
    const handler: EventCallback<T> = ((data: Parameters<EventCallback<T>>[0]) => {
      callbackRef.current(data);
    }) as EventCallback<T>;

    // subscribe() returns an unsubscribe function – perfect for cleanup.
    const unsubscribe = wsManager.subscribe(event, handler);

    return unsubscribe;
  }, [event]);
}
