"""Append-only event log. Every event is committed before subscribers are notified."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime

from replayforge.redaction import redact

from replayforge_api.db import Event, session_scope

EVENT_SCHEMA_VERSION = "1.0"


class EventBus:
    def __init__(self) -> None:
        self._signals: defaultdict[str, asyncio.Event] = defaultdict(asyncio.Event)

    def publish(
        self,
        experiment_id: str,
        type_: str,
        payload: dict | None = None,
        *,
        actor_type: str = "system",
        actor_id: str | None = None,
    ) -> dict:
        clean = _redact_payload(payload or {})
        with session_scope() as session:
            event = Event(
                experiment_id=experiment_id,
                type=type_,
                actor_type=actor_type,
                actor_id=actor_id,
                payload_json=clean,
                created_at=datetime.now(UTC),
            )
            session.add(event)
            session.flush()
            envelope = serialize(event)
        signal = self._signals[experiment_id]
        signal.set()
        self._signals[experiment_id] = asyncio.Event()
        return envelope

    def signal_for(self, experiment_id: str) -> asyncio.Event:
        return self._signals[experiment_id]


def serialize(event: Event) -> dict:
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_id": event.id,
        "seq": event.seq,
        "experiment_id": event.experiment_id,
        "type": event.type,
        "actor_type": event.actor_type,
        "actor_id": event.actor_id,
        "occurred_at": event.created_at.isoformat() if event.created_at else None,
        "payload": event.payload_json,
    }


def _redact_payload(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: _redact_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_payload(v) for v in value]
    return value


bus = EventBus()
