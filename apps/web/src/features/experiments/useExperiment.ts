import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useReducer, useRef, useState } from "react";

import { api } from "../../api/client";
import type { ReplayEvent } from "../../api/types";
import { applyEvent, emptyState, hydrate, type LabState } from "./labState";

type Action = { type: "hydrate"; state: LabState } | { type: "event"; event: ReplayEvent };

function reducer(state: LabState, action: Action): LabState {
  if (action.type === "hydrate") {
    // Keep live notifications; take persisted truth for everything else.
    return action.state.lastSeq >= state.lastSeq ? { ...action.state, notifications: state.notifications } : state;
  }
  return applyEvent(state, action.event);
}

const REFRESH_ON = new Set(["case.completed", "case.failed", "metrics.updated", "policy.evaluated", "experiment.completed", "experiment.failed", "experiment.cancelled", "github.delivery.completed", "github.delivery.failed"]);

export function useExperiment(experimentId: string) {
  const queryClient = useQueryClient();
  const snapshot = useQuery({ queryKey: ["experiment", experimentId], queryFn: () => api.experiment(experimentId) });
  const [state, dispatch] = useReducer(reducer, undefined, emptyState);
  const [events, setEvents] = useState<ReplayEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const hydrated = useRef(false);
  const refreshTimer = useRef<number | null>(null);

  useEffect(() => {
    if (snapshot.data) {
      dispatch({ type: "hydrate", state: hydrate(snapshot.data) });
      hydrated.current = true;
    }
  }, [snapshot.data]);

  useEffect(() => {
    // Replay the persisted log once so the timeline is complete after a refresh.
    fetch(`/api/experiments/${experimentId}/event-log`).then((r) => r.json()).then((log: ReplayEvent[]) => setEvents(log)).catch(() => undefined);
  }, [experimentId]);

  useEffect(() => {
    if (!snapshot.data) return;
    // EventSource sends Last-Event-ID automatically on reconnect; ?after= covers the first connection.
    const source = new EventSource(`/api/experiments/${experimentId}/events?after=${snapshot.data.last_event_seq}`);
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener("replayforge", (message) => {
      const event = JSON.parse((message as MessageEvent).data) as ReplayEvent;
      dispatch({ type: "event", event });
      setEvents((current) => (current.some((e) => e.seq === event.seq) ? current : [...current, event]));
      if (REFRESH_ON.has(event.type)) {
        if (refreshTimer.current) window.clearTimeout(refreshTimer.current);
        refreshTimer.current = window.setTimeout(() => queryClient.invalidateQueries({ queryKey: ["experiment", experimentId] }), 250);
      }
    });
    return () => source.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [experimentId, Boolean(snapshot.data)]);

  return { snapshot, state, events, connected };
}
