"""Deterministic migration policy. An LLM may summarize a decision but can never change it."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

POLICY_VERSION = "rf-policy-1"
Outcome = Literal["pass", "warn", "block"]


class MigrationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_pass_rate_drop: float = Field(default=0.02, ge=0.0, le=1.0)
    critical_tasks_must_pass: bool = True
    max_p95_latency_ms: float | None = Field(default=15000, gt=0)
    require_lower_cost_per_success: bool = False
    max_provider_error_rate: float = Field(default=0.02, ge=0.0, le=1.0)


@dataclass(frozen=True, slots=True)
class Violation:
    rule: str
    severity: Literal["warn", "block"]
    message: str
    evidence: dict[str, object]


@dataclass(frozen=True, slots=True)
class Decision:
    outcome: Outcome
    violations: tuple[Violation, ...]
    policy_version: str = POLICY_VERSION

    def as_dict(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "policy_version": self.policy_version,
            "violations": [asdict(v) for v in self.violations],
        }


@dataclass(frozen=True, slots=True)
class PairFact:
    task_id: str
    critical: bool
    baseline_passed: bool
    candidate_passed: bool


def _metric(metrics: Sequence[dict[str, object]], lane: str, name: str) -> float | None:
    for metric in metrics:
        if metric["lane"] == lane and metric["name"] == name:
            value = metric["value"]
            return float(value) if isinstance(value, int | float) else None
    return None


def evaluate_policy(
    policy: MigrationPolicy, pairs: Sequence[PairFact], metrics: Sequence[dict[str, object]]
) -> Decision:
    """Rules and severities:

    block: pass-rate drop above the limit, a critical task failing on the candidate, or candidate
           provider errors above the limit (the comparison itself is unreliable).
    warn:  p95 latency above the ceiling, or cost per success not lower when required
           (including unknown cost, which cannot demonstrate a saving).
    """

    violations: list[Violation] = []
    if not pairs:
        return Decision("block", (Violation("comparable_pairs", "block", "no comparable pairs", {}),))
    n = len(pairs)
    base_rate = sum(p.baseline_passed for p in pairs) / n
    cand_rate = sum(p.candidate_passed for p in pairs) / n
    drop = base_rate - cand_rate
    if drop > policy.max_pass_rate_drop + 1e-12:
        violations.append(
            Violation(
                "max_pass_rate_drop",
                "block",
                f"candidate pass rate {cand_rate:.0%} is {drop:.0%} below baseline {base_rate:.0%} (limit {policy.max_pass_rate_drop:.0%})",
                {"baseline": base_rate, "candidate": cand_rate, "n": n},
            )
        )
    if policy.critical_tasks_must_pass:
        failing = sorted(p.task_id for p in pairs if p.critical and not p.candidate_passed)
        if failing:
            violations.append(
                Violation(
                    "critical_tasks_must_pass",
                    "block",
                    f"critical tasks failing on candidate: {', '.join(failing)}",
                    {"tasks": failing},
                )
            )
    error_rate = _metric(metrics, "candidate", "provider_error_rate")
    if error_rate is not None and error_rate > policy.max_provider_error_rate + 1e-12:
        violations.append(
            Violation(
                "max_provider_error_rate",
                "block",
                f"candidate provider error rate {error_rate:.0%} exceeds {policy.max_provider_error_rate:.0%}",
                {"provider_error_rate": error_rate},
            )
        )
    if policy.max_p95_latency_ms is not None:
        p95 = _metric(metrics, "candidate", "latency_p95_ms")
        if p95 is not None and p95 > policy.max_p95_latency_ms:
            violations.append(
                Violation(
                    "max_p95_latency_ms",
                    "warn",
                    f"candidate p95 latency {p95:.0f} ms exceeds {policy.max_p95_latency_ms:.0f} ms",
                    {"p95_ms": p95},
                )
            )
    if policy.require_lower_cost_per_success:
        base_cost = _metric(metrics, "baseline", "cost_per_success_usd")
        cand_cost = _metric(metrics, "candidate", "cost_per_success_usd")
        if base_cost is None or cand_cost is None:
            violations.append(
                Violation(
                    "require_lower_cost_per_success",
                    "warn",
                    "cost per success is unknown for at least one lane, so a saving cannot be shown",
                    {"baseline": base_cost, "candidate": cand_cost},
                )
            )
        elif cand_cost >= base_cost:
            violations.append(
                Violation(
                    "require_lower_cost_per_success",
                    "warn",
                    f"candidate cost per success ${cand_cost:.4f} is not lower than baseline ${base_cost:.4f}",
                    {"baseline": base_cost, "candidate": cand_cost},
                )
            )
    outcome: Outcome = "block" if any(v.severity == "block" for v in violations) else ("warn" if violations else "pass")
    return Decision(outcome, tuple(violations))


GITHUB_CONCLUSION = {"pass": "success", "warn": "neutral", "block": "failure"}
