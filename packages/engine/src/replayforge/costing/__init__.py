"""Latency and cost metrics with explicit measurement labels.

measurement_kind:
- measured: timed by ReplayForge (wall-clock latency).
- provider_reported: returned by the provider (token usage).
- derived: arithmetic over reported usage and a dated price snapshot.
- estimated: anything else. Unknown values stay None, never zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

from benchtrace.stats import pass_rate_interval
from benchtrace.trace import TraceRecord

MIN_LATENCY_SAMPLES = 5


@dataclass(frozen=True, slots=True)
class Metric:
    lane: str
    name: str
    value: float | None
    unit: str
    measurement_kind: str
    sample_count: int
    source: str
    detail: dict[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _quantile(values: Sequence[float], q: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def lane_metrics(lane: str, traces: Sequence[TraceRecord]) -> list[Metric]:
    n = len(traces)
    metrics: list[Metric] = []
    if n == 0:
        return metrics
    outcomes = [t.passed for t in traces]
    estimate = pass_rate_interval(outcomes)
    metrics.append(
        Metric(
            lane,
            "pass_rate",
            estimate.value,
            "ratio",
            "measured",
            n,
            "deterministic graders",
            {"lower": estimate.lower, "upper": estimate.upper, "confidence": estimate.confidence},
        )
    )
    provider_errors = sum(1 for t in traces if t.failure and t.failure.kind == "provider_error")
    metrics.append(
        Metric(
            lane,
            "provider_error_rate",
            provider_errors / n,
            "ratio",
            "measured",
            n,
            "case failures",
        )
    )
    latencies = [t.latency_ms for t in traces if t.failure is None or t.failure.kind != "provider_error"]
    enough = len(latencies) >= MIN_LATENCY_SAMPLES
    metrics.append(
        Metric(
            lane,
            "latency_p50_ms",
            _quantile(latencies, 0.5) if enough else None,
            "ms",
            "measured",
            len(latencies),
            "case wall clock",
        )
    )
    metrics.append(
        Metric(
            lane,
            "latency_p95_ms",
            _quantile(latencies, 0.95) if enough else None,
            "ms",
            "measured",
            len(latencies),
            "case wall clock",
        )
    )
    input_tokens = sum(t.usage.input_tokens for t in traces)
    output_tokens = sum(t.usage.output_tokens for t in traces)
    usage_reported = any(t.usage.input_tokens or t.usage.output_tokens for t in traces)
    metrics.append(
        Metric(
            lane,
            "input_tokens",
            float(input_tokens) if usage_reported else None,
            "tokens",
            "provider_reported",
            n,
            "provider usage fields",
        )
    )
    metrics.append(
        Metric(
            lane,
            "output_tokens",
            float(output_tokens) if usage_reported else None,
            "tokens",
            "provider_reported",
            n,
            "provider usage fields",
        )
    )
    calls = [c for t in traces for c in t.model_calls]
    priced = bool(calls) and all(c.pricing_known for c in calls) and usage_reported
    total_cost = sum(c.cost_usd for c in calls) if priced else None
    versions = sorted({c.pricing_version or "" for c in calls if c.pricing_version})
    successes = sum(outcomes)
    metrics.append(
        Metric(
            lane,
            "cost_attempted_usd",
            total_cost,
            "usd",
            "derived" if priced else "estimated",
            n,
            "usage x dated price snapshot" if priced else "price unknown for this model",
            {"pricing_versions": versions},
        )
    )
    metrics.append(
        Metric(
            lane,
            "cost_per_success_usd",
            (total_cost / successes) if (priced and total_cost is not None and successes) else None,
            "usd",
            "derived" if priced else "estimated",
            successes,
            "attempted cost / successful cases" if priced else "price unknown for this model",
        )
    )
    metrics.append(Metric(lane, "model_calls", float(len(calls)), "calls", "measured", n, "trace model_calls"))
    return metrics
