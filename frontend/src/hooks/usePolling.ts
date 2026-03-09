import { useState, useEffect, useRef } from "react";

interface UsePollingResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function usePolling<T>(
  url: string,
  intervalMs: number = 30000
): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const isInitialFetch = useRef(true);

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval>;
    let cancelled = false;

    const fetchData = async () => {
      if (isInitialFetch.current) {
        setLoading(true);
      }

      try {
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const json = (await response.json()) as T;
        if (!cancelled) {
          setData(json);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "An unknown error occurred"
          );
        }
      } finally {
        if (!cancelled) {
          if (isInitialFetch.current) {
            isInitialFetch.current = false;
            setLoading(false);
          }
        }
      }
    };

    fetchData();
    intervalId = setInterval(fetchData, intervalMs);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [url, intervalMs]);

  return { data, loading, error };
}
