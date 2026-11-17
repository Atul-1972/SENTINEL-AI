import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../services/api";

export function useDashboard() {
  const [state, setState] = useState({
    health: null,
    stats: null,
    model: null,
    alerts: [],
    history: [],
    updatedAt: null,
    error: "",
    loading: true,
  });
  const [autoRefresh, setAutoRefresh] = useState(true);
  const busy = useRef(false);
  const mounted = useRef(false);
  const refresh = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    if (mounted.current) setState((prev) => ({ ...prev, loading: true }));
    const results = await Promise.allSettled([
      api.health(),
      api.stats(),
      api.modelInfo(),
      api.alerts(),
      api.history(),
    ]);
    if (mounted.current)
      setState((prev) => {
        const next = { ...prev, loading: false };
        ["health", "stats", "model", "alerts", "history"].forEach(
          (name, index) => {
            if (results[index].status === "fulfilled")
              next[name] = results[index].value;
            else if (name === "health") next.health = null;
          },
        );
        const failures = results.filter(
          (result) => result.status === "rejected",
        );
        next.error = failures.length
          ? failures[0].reason.message || "Cannot reach the API."
          : "";
        if (!failures.length) next.updatedAt = new Date().toISOString();
        return next;
      });
    busy.current = false;
  }, []);
  useEffect(() => {
    mounted.current = true;
    refresh();
    return () => {
      mounted.current = false;
    };
  }, [refresh]);
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(() => {
      if (!document.hidden) refresh();
    }, 15000);
    return () => clearInterval(id);
  }, [autoRefresh, refresh]);
  return { ...state, autoRefresh, setAutoRefresh, refresh };
}
