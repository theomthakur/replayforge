"""Paired experiment execution and analysis, independent of persistence.

The API wraps this with a database and event stream; the CLI uses it directly.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from benchtrace.providers import Provider
from benchtrace.stats import compare_paired

from replayforge.cassettes.schema import LoadedSuite, TaskSpec
from replayforge.costing import lane_metrics
from replayforge.investigation import Finding, needs_investigation, pair_outcome, rule_investigate
from replayforge.orchestration.case import CaseResult, run_case
from replayforge.policy import Decision, MigrationPolicy, PairFact, evaluate_policy
from replayforge.providers import LaneConfig, build_provider

LANES = ("baseline", "candidate")
CaseCallback = Callable[[CaseResult], Awaitable[None]]


async def _ignore(_result: CaseResult) -> None:
    return None


@dataclass(slots=True)
class PairResult:
    task: TaskSpec
    baseline: CaseResult
    candidate: CaseResult
    outcome: str
    finding: Finding | None = None


@dataclass(slots=True)
class ExperimentResult:
    run_id: str
    suite_digest: str
    pairs: list[PairResult]
    metrics: list[dict[str, object]]
    comparison: dict[str, object] | None
    decision: Decision
    lane_labels: dict[str, str] = field(default_factory=dict)


def select_tasks(suite: LoadedSuite, task_ids: Sequence[str] | None) -> list[TaskSpec]:
    if not task_ids:
        return list(suite.cassette.tasks)
    return [suite.cassette.task(task_id) for task_id in task_ids]


async def run_lanes(
    suite: LoadedSuite,
    tasks: Sequence[TaskSpec],
    lanes: dict[str, LaneConfig],
    providers: dict[str, Provider],
    *,
    run_id: str,
    concurrency: int = 3,
    sandbox_backend: str = "local",
    on_result: CaseCallback = _ignore,
    skip: set[tuple[str, str]] | None = None,
) -> list[CaseResult]:
    """Run every (task, lane) concurrently with a per-lane semaphore. Skips already-completed keys."""

    semaphores = {lane: asyncio.Semaphore(concurrency) for lane in lanes}
    done = skip or set()
    results: list[CaseResult] = []

    async def one(task: TaskSpec, lane: str) -> None:
        async with semaphores[lane]:
            result = await run_case(
                run_id=run_id,
                suite=suite,
                task=task,
                lane_name=lane,
                lane=lanes[lane],
                provider=providers[lane],
                sandbox_backend=sandbox_backend,
            )
            results.append(result)
            await on_result(result)

    async with asyncio.TaskGroup() as group:
        for task in tasks:
            for lane in lanes:
                if (task.id, lane) not in done:
                    group.create_task(one(task, lane))
    return results


def analyze(
    suite: LoadedSuite,
    tasks: Sequence[TaskSpec],
    results: Sequence[CaseResult],
    policy: MigrationPolicy,
    run_id: str,
) -> ExperimentResult:
    by_key = {(r.task_id, r.lane): r for r in results}
    pairs: list[PairResult] = []
    for task in tasks:
        base, cand = by_key.get((task.id, "baseline")), by_key.get((task.id, "candidate"))
        if base is None or cand is None or base.grader_version != cand.grader_version:
            continue
        outcome = pair_outcome(base.passed, cand.passed)
        finding = (
            rule_investigate(cand.run.trace, base.run.trace)
            if needs_investigation(base.run.trace, cand.run.trace) and not cand.passed
            else None
        )
        pairs.append(PairResult(task, base, cand, outcome, finding))
    metrics: list[dict[str, object]] = []
    for lane in LANES:
        metrics.extend(m.as_dict() for m in lane_metrics(lane, [r.run.trace for r in results if r.lane == lane]))
    comparison = None
    if pairs:
        stats = compare_paired(
            [p.baseline.passed for p in pairs],
            [p.candidate.passed for p in pairs],
            model_a="baseline",
            model_b="candidate",
        )
        comparison = {
            "n": stats.n,
            "baseline_pass_rate": stats.pass_rate_a.value,
            "candidate_pass_rate": stats.pass_rate_b.value,
            "difference": stats.difference.value,
            "difference_interval": [stats.difference.lower, stats.difference.upper],
            "baseline_only_passed": stats.a_only_passed,
            "candidate_only_passed": stats.b_only_passed,
            "mcnemar_p_value": stats.p_value,
            "conclusion": stats.conclusion,
        }
    facts = [PairFact(p.task.id, p.task.critical, p.baseline.passed, p.candidate.passed) for p in pairs]
    decision = evaluate_policy(policy, facts, metrics)
    return ExperimentResult(run_id, suite.digest, pairs, metrics, comparison, decision)


async def run_experiment(
    suite: LoadedSuite,
    baseline: LaneConfig,
    candidate: LaneConfig,
    *,
    policy: MigrationPolicy | None = None,
    task_ids: Sequence[str] | None = None,
    concurrency: int = 3,
    solutions_dir: Path | None = None,
    sandbox_backend: str = "local",
    on_result: CaseCallback = _ignore,
) -> ExperimentResult:
    run_id = uuid4().hex
    tasks = select_tasks(suite, task_ids)
    solutions = solutions_dir or suite.fixture_path.parent.parent / "solutions"
    lanes = {"baseline": baseline, "candidate": candidate}
    providers = {
        name: build_provider(cfg, cassette=suite.cassette, solutions_dir=solutions, max_concurrency=concurrency)
        for name, cfg in lanes.items()
    }
    try:
        results = await run_lanes(
            suite,
            tasks,
            lanes,
            providers,
            run_id=run_id,
            concurrency=concurrency,
            sandbox_backend=sandbox_backend,
            on_result=on_result,
        )
    finally:
        for provider in providers.values():
            close = getattr(provider, "aclose", None)
            if close:
                await close()
    result = analyze(suite, tasks, results, policy or MigrationPolicy(), run_id)
    result.lane_labels = {name: cfg.label() for name, cfg in lanes.items()}
    return result
