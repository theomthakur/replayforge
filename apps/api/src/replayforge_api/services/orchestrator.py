"""Experiment lifecycle: validate, run paired lanes with persistence, analyze, decide.

State machine: draft -> ready -> running -> investigating -> deciding -> completed
               running -> cancelled | failed
Completed case runs are unique per (experiment, task, case, repeat, lane), so a restarted process
resumes without duplicating work.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import UTC, datetime

from benchtrace.trace import TraceRecord
from replayforge.cassettes import load_suite
from replayforge.cassettes.schema import LoadedSuite, TaskSpec
from replayforge.grading.coding import GRADER_VERSION
from replayforge.investigation import rule_investigate
from replayforge.orchestration.agent import AgentRun, ToolStepRecord
from replayforge.orchestration.case import CaseResult
from replayforge.orchestration.paired import analyze, run_lanes, select_tasks
from replayforge.policy import MigrationPolicy
from replayforge.providers import LaneConfig, build_provider
from sqlalchemy import select

from replayforge_api.config import get_settings
from replayforge_api.db import (
    CaseRun,
    Experiment,
    Grade,
    Investigation,
    Metric,
    PairComparison,
    ReleaseDecision,
    Suite,
    ToolStep,
    session_scope,
)
from replayforge_api.events import bus

log = logging.getLogger("replayforge.orchestrator")
_tasks: dict[str, asyncio.Task[None]] = {}


def lane_from_json(data: dict) -> LaneConfig:
    return LaneConfig(**{k: v for k, v in data.items() if k in LaneConfig.__dataclass_fields__})


def estimate(suite: LoadedSuite, task_ids: list[str] | None) -> dict:
    tasks = select_tasks(suite, task_ids)
    max_calls = sum(suite.cassette.limits_for(t).max_steps for t in tasks) * 2
    settings = get_settings()
    return {
        "cases": len(tasks),
        "lanes": 2,
        "max_provider_calls": max_calls,
        "limit_provider_calls": settings.max_provider_calls,
        "limit_cases": settings.max_experiment_cases,
        "within_budget": max_calls <= settings.max_provider_calls and len(tasks) <= settings.max_experiment_cases,
        "note": "Upper bound: every case uses its full step budget on both lanes. Spend in USD is unknown until the provider's price is configured.",
    }


def _load(experiment_id: str) -> tuple[Experiment, LoadedSuite]:
    with session_scope() as session:
        experiment = session.get(Experiment, experiment_id)
        if experiment is None:
            raise KeyError(experiment_id)
        suite_row = session.get(Suite, experiment.suite_id)
        assert suite_row is not None
        source = suite_row.source_revision
    suite = load_suite(source)
    if suite.digest != suite_row.digest:
        raise RuntimeError("suite content changed since the experiment was created; digest mismatch")
    return experiment, suite


def _set_status(experiment_id: str, status: str, **fields: object) -> None:
    with session_scope() as session:
        experiment = session.get(Experiment, experiment_id)
        assert experiment is not None
        experiment.status = status
        for key, value in fields.items():
            setattr(experiment, key, value)


def start(experiment_id: str) -> None:
    if experiment_id in _tasks and not _tasks[experiment_id].done():
        return
    _tasks[experiment_id] = asyncio.create_task(_run(experiment_id))


def cancel(experiment_id: str) -> bool:
    task = _tasks.get(experiment_id)
    if task and not task.done():
        task.cancel()
        return True
    return False


def resume_incomplete() -> list[str]:
    with session_scope() as session:
        ids = [
            e.id
            for e in session.scalars(
                select(Experiment).where(Experiment.status.in_(["running", "investigating", "deciding"]))
            )
        ]
    for experiment_id in ids:
        bus.publish(experiment_id, "experiment.resumed", {"reason": "process restart"})
        start(experiment_id)
    return ids


def _persist_case(experiment_id: str, result: CaseResult, lane_config: LaneConfig) -> str:
    trace = result.run.trace
    with session_scope() as session:
        existing = session.scalar(
            select(CaseRun).where(
                CaseRun.experiment_id == experiment_id,
                CaseRun.task_id == result.task_id,
                CaseRun.case_id == result.case_id,
                CaseRun.repeat_index == result.repeat,
                CaseRun.lane == result.lane,
            )
        )
        if existing:
            return existing.id
        run = CaseRun(
            experiment_id=experiment_id,
            task_id=result.task_id,
            case_id=result.case_id,
            repeat_index=result.repeat,
            lane=result.lane,
            status=trace.status,
            passed=trace.passed,
            provider=trace.provider,
            model=trace.model,
            seed=lane_config.seed,
            started_at=trace.started_at,
            completed_at=trace.completed_at,
            latency_ms=trace.latency_ms,
            input_tokens=trace.usage.input_tokens,
            output_tokens=trace.usage.output_tokens,
            provider_cost=trace.cost_usd
            if trace.model_calls and all(c.pricing_known for c in trace.model_calls)
            else None,
            failure_mode=trace.failure.kind if trace.failure else None,
            finish_summary=result.run.finish_summary,
            grader_version=result.grader_version,
            trace_json=trace.model_dump(mode="json"),
        )
        session.add(run)
        session.flush()
        for step in result.run.steps:
            session.add(
                ToolStep(
                    case_run_id=run.id,
                    sequence=step.sequence,
                    tool_name=step.tool,
                    arguments_json=step.arguments,
                    observation_json=step.observation,
                    ok=step.ok,
                    error_kind=step.error_kind,
                    exit_code=step.exit_code,
                    duration_ms=step.duration_ms,
                )
            )
        for grade in trace.grader_outputs:
            metadata = grade.metadata or {}
            session.add(
                Grade(
                    case_run_id=run.id,
                    grader_type=grade.grader,
                    grader_version=str(metadata.get("version", GRADER_VERSION)),
                    score=grade.score,
                    passed=grade.score == 1.0,
                    reason=grade.reason,
                    evidence_json=metadata.get("evidence", {}) if isinstance(metadata.get("evidence"), dict) else {},
                )
            )
        return run.id


def _rehydrate(experiment_id: str) -> list[CaseResult]:
    """Rebuild engine results from persisted case runs (used to resume and to re-analyze)."""

    results: list[CaseResult] = []
    with session_scope() as session:
        runs = session.scalars(select(CaseRun).where(CaseRun.experiment_id == experiment_id)).all()
        for row in runs:
            steps = [
                ToolStepRecord(
                    s.sequence,
                    s.tool_name,
                    s.arguments_json,
                    s.ok,
                    s.error_kind,
                    s.observation_json,
                    s.exit_code,
                    s.duration_ms,
                )
                for s in session.scalars(
                    select(ToolStep).where(ToolStep.case_run_id == row.id).order_by(ToolStep.sequence)
                )
            ]
            trace = TraceRecord.model_validate(row.trace_json)
            results.append(
                CaseResult(
                    row.lane,
                    row.task_id,
                    row.case_id,
                    row.repeat_index,
                    AgentRun(
                        trace=trace, steps=steps, finish_summary=row.finish_summary, failure_kind=row.failure_mode
                    ),
                    row.grader_version,
                )
            )
    return results


async def _run(experiment_id: str) -> None:
    try:
        experiment, suite = _load(experiment_id)
        lanes = {
            "baseline": lane_from_json(experiment.baseline_config_json),
            "candidate": lane_from_json(experiment.candidate_config_json),
        }
        tasks = select_tasks(suite, experiment.task_ids_json or None)
        settings = get_settings()
        already = {(r.task_id, r.lane) for r in _rehydrate(experiment_id)}
        if experiment.status in ("ready", "draft"):
            _set_status(experiment_id, "running", started_at=datetime.now(UTC))
            bus.publish(experiment_id, "experiment.started", {"cases": len(tasks), "lanes": list(lanes)})
            for lane in lanes:
                bus.publish(experiment_id, "lane.started", {"lane": lane, "label": lanes[lane].label()})
            for task in tasks:
                for lane in lanes:
                    bus.publish(
                        experiment_id,
                        "case.queued",
                        {"task_id": task.id, "lane": lane, "critical": task.critical, "category": task.category},
                    )
        providers = {
            name: build_provider(
                cfg,
                cassette=suite.cassette,
                solutions_dir=settings.solutions_dir,
                max_concurrency=settings.max_concurrency,
            )
            for name, cfg in lanes.items()
        }

        def sink_for(task: TaskSpec, lane: str):
            async def sink(type_: str, payload: dict) -> None:
                bus.publish(
                    experiment_id,
                    type_,
                    {"task_id": task.id, "lane": lane, **payload},
                    actor_type="agent",
                    actor_id=f"{lane}-runner",
                )

            return sink

        async def on_result(result: CaseResult) -> None:
            _persist_case(experiment_id, result, lanes[result.lane])
            trace = result.run.trace
            bus.publish(
                experiment_id,
                "case.completed" if trace.status == "completed" else "case.failed",
                {
                    "task_id": result.task_id,
                    "lane": result.lane,
                    "passed": result.passed,
                    "failure_mode": trace.failure.kind if trace.failure else None,
                    "latency_ms": round(trace.latency_ms, 1),
                    "tool_calls": len(result.run.steps),
                },
                actor_type="agent",
                actor_id="judge",
            )

        try:
            await run_lanes(
                suite,
                tasks,
                lanes,
                providers,
                run_id=experiment_id,
                concurrency=settings.max_concurrency,
                sandbox_backend=settings.sandbox_backend,
                on_result=on_result,
                skip=already,
                event_sink_for=sink_for,
            )
        finally:
            for provider in providers.values():
                close = getattr(provider, "aclose", None)
                if close:
                    await close()
        await _finalize(experiment_id, suite, tasks, MigrationPolicy(**experiment.policy_json))
    except asyncio.CancelledError:
        _set_status(experiment_id, "cancelled", completed_at=datetime.now(UTC))
        bus.publish(experiment_id, "experiment.cancelled", {})
        raise
    except Exception as error:  # noqa: BLE001 - recorded, not swallowed silently
        log.exception("experiment %s failed", experiment_id)
        _set_status(experiment_id, "failed", error=str(error)[:500], completed_at=datetime.now(UTC))
        bus.publish(experiment_id, "experiment.failed", {"error": str(error)[:500]})


async def _finalize(experiment_id: str, suite: LoadedSuite, tasks: list[TaskSpec], policy: MigrationPolicy) -> None:
    _set_status(experiment_id, "investigating")
    results = _rehydrate(experiment_id)
    result = analyze(suite, tasks, results, policy, experiment_id)
    with session_scope() as session:
        run_ids = {
            (r.task_id, r.lane): r.id
            for r in session.scalars(select(CaseRun).where(CaseRun.experiment_id == experiment_id))
        }
        for old in session.scalars(select(PairComparison).where(PairComparison.experiment_id == experiment_id)):
            session.delete(old)
        for old in session.scalars(select(Metric).where(Metric.experiment_id == experiment_id)):
            session.delete(old)
    for pair in result.pairs:
        with session_scope() as session:
            base_steps = [s.tool for s in pair.baseline.run.steps]
            cand_steps = [s.tool for s in pair.candidate.run.steps]
            row = PairComparison(
                experiment_id=experiment_id,
                task_id=pair.task.id,
                critical=pair.task.critical,
                baseline_run_id=run_ids[(pair.task.id, "baseline")],
                candidate_run_id=run_ids[(pair.task.id, "candidate")],
                outcome=pair.outcome,
                trajectory_delta_json={
                    "baseline_tools": base_steps,
                    "candidate_tools": cand_steps,
                    "step_delta": len(cand_steps) - len(base_steps),
                },
            )
            session.add(row)
            session.flush()
            pair_id = row.id
        bus.publish(
            experiment_id,
            "pair.comparable",
            {"task_id": pair.task.id, "outcome": pair.outcome, "critical": pair.task.critical},
        )
        if pair.finding:
            bus.publish(
                experiment_id,
                "investigation.started",
                {"task_id": pair.task.id},
                actor_type="agent",
                actor_id="investigator",
            )
            finding = pair.finding or rule_investigate(pair.candidate.run.trace)
            with session_scope() as session:
                session.add(
                    Investigation(
                        pair_comparison_id=pair_id,
                        category=finding.category,
                        confidence=finding.confidence,
                        summary=finding.summary,
                        evidence_refs_json=list(finding.evidence_refs),
                        method=finding.method,
                        model=finding.model,
                        prompt_version=finding.prompt_version,
                    )
                )
            bus.publish(
                experiment_id,
                "investigation.completed",
                {
                    "task_id": pair.task.id,
                    "category": finding.category,
                    "method": finding.method,
                    "summary": finding.summary,
                },
                actor_type="agent",
                actor_id="investigator",
            )
    with session_scope() as session:
        for metric in result.metrics:
            session.add(
                Metric(
                    experiment_id=experiment_id,
                    lane=str(metric["lane"]),
                    name=str(metric["name"]),
                    value=metric["value"],
                    unit=str(metric["unit"]),
                    measurement_kind=str(metric["measurement_kind"]),
                    sample_count=int(metric["sample_count"]),
                    source=str(metric["source"]),
                    detail_json=metric.get("detail"),
                )
            )
        experiment = session.get(Experiment, experiment_id)
        assert experiment is not None
        experiment.comparison_json = result.comparison
    bus.publish(
        experiment_id, "metrics.updated", {"metrics": result.metrics}, actor_type="agent", actor_id="cost-profiler"
    )
    _set_status(experiment_id, "deciding")
    decision = result.decision
    summary = decision_summary(result.comparison, decision.as_dict())
    with session_scope() as session:
        existing = session.scalar(select(ReleaseDecision).where(ReleaseDecision.experiment_id == experiment_id))
        if existing is None:
            existing = ReleaseDecision(
                experiment_id=experiment_id,
                outcome=decision.outcome,
                violations_json=[],
                summary="",
                policy_version=decision.policy_version,
            )
            session.add(existing)
        existing.outcome = decision.outcome
        existing.violations_json = [asdict(v) for v in decision.violations]
        existing.summary = summary
        existing.policy_version = decision.policy_version
    bus.publish(
        experiment_id,
        "policy.evaluated",
        {"outcome": decision.outcome, "violations": [asdict(v) for v in decision.violations], "summary": summary},
        actor_type="agent",
        actor_id="release-gate",
    )
    _set_status(experiment_id, "completed", completed_at=datetime.now(UTC))
    bus.publish(experiment_id, "experiment.completed", {"outcome": decision.outcome})


def decision_summary(comparison: dict | None, decision: dict) -> str:
    outcome = str(decision["outcome"]).upper()
    if not comparison:
        return f"{outcome}: no comparable pairs."
    parts = [
        f"{outcome}: candidate {comparison['candidate_pass_rate']:.0%} vs baseline {comparison['baseline_pass_rate']:.0%} on {comparison['n']} paired cases"
    ]
    violations = decision.get("violations") or []
    if violations:
        parts.append("; ".join(str(v["message"]) for v in violations))
    return ". ".join(parts) + "."
