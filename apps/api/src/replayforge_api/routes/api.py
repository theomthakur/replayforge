"""REST API. Mutations accept an Idempotency-Key header."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from replayforge.cassettes import CassetteError, load_suite
from replayforge.policy import MigrationPolicy
from replayforge.provenance import git_revision
from replayforge.providers import FIXTURE_PROFILES, NebiusTokenFactoryProvider, local_base_url
from replayforge.report import render_markdown
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from replayforge_api.config import get_settings
from replayforge_api.db import (
    CaseRun,
    Event,
    Experiment,
    Grade,
    Investigation,
    Metric,
    PairComparison,
    Project,
    ReleaseDecision,
    Suite,
    ToolStep,
    WebhookDelivery,
    session_scope,
)
from replayforge_api.events import bus, serialize
from replayforge_api.github import GitHubClient, GitHubError, check_run_payload, parse_pr_url, verify_signature
from replayforge_api.pdf_report import render_pdf
from replayforge_api.services import orchestrator

router = APIRouter()

FIXTURE_MODELS = [
    {"provider": "fixture", "model": "fixture/reference", "label": "Fixture: reference solutions (not a model)"},
    {
        "provider": "fixture",
        "model": "fixture/variant",
        "label": "Fixture: scripted variant with two regressions (not a model)",
    },
]


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.get("/ready")
def ready() -> dict:
    with session_scope() as session:
        session.execute(select(1))
    settings = get_settings()
    return {"ok": True, "missing_configuration": settings.missing(), "sandbox_backend": settings.sandbox_backend}


@router.get("/api/models")
async def models() -> dict:
    local_models = [name.strip() for name in os.environ.get("REPLAYFORGE_LOCAL_MODELS", "").split(",") if name.strip()]
    result: dict = {
        "fixture": FIXTURE_MODELS,
        "nebius": {"configured": False, "models": []},
        "baseline": [],
        "local": [{"provider": "local", "model": name, "label": f"Local: {name}"} for name in local_models],
    }
    if os.environ.get("BASELINE_MODEL"):
        result["baseline"].append(
            {"provider": "benchtrace", "model": os.environ["BASELINE_MODEL"], "label": os.environ["BASELINE_MODEL"]}
        )
    provider = NebiusTokenFactoryProvider()
    if not provider.configured:
        result["nebius"]["reason"] = "NEBIUS_TOKEN_FACTORY_API_KEY is not set on the server"
        return result
    try:
        catalog = await provider.list_models()
        result["nebius"] = {
            "configured": True,
            "fetched_at": catalog.fetched_at.isoformat(),
            "models": [
                {"provider": "nebius", "model": m.id, "owned_by": m.owned_by, "nvidia": m.is_nvidia}
                for m in catalog.models
            ],
        }
    except Exception as error:  # noqa: BLE001 - surfaced to the UI as a notification
        result["nebius"] = {"configured": True, "error": str(error)[:300], "models": []}
    finally:
        await provider.aclose()
    return result


def _default_project() -> str:
    with session_scope() as session:
        project = session.scalar(select(Project).where(Project.name == "Demo project"))
        if project is None:
            project = Project(name="Demo project")
            session.add(project)
            session.flush()
        return project.id


class SuiteRequest(BaseModel):
    path: str = Field(default="demo-suite.yaml", description="File name inside fixtures/suites")


def _suite_path(name: str) -> Path:
    settings = get_settings()
    candidate = (settings.suites_dir / Path(name).name).resolve()
    if settings.suites_dir.resolve() not in candidate.parents or not candidate.is_file():
        raise HTTPException(404, "suite not found")
    return candidate


@router.get("/api/suites/available")
def available_suites() -> list[dict]:
    items = []
    for path in sorted(get_settings().suites_dir.glob("*.yaml")):
        try:
            suite = load_suite(path)
            items.append(
                {
                    "file": path.name,
                    "id": suite.cassette.suite.id,
                    "name": suite.cassette.suite.name,
                    "tasks": len(suite.cassette.tasks),
                    "digest": suite.digest,
                    "source_repository_url": suite.cassette.suite.source_repository_url,
                    "source_revision": suite.cassette.suite.source_revision,
                }
            )
        except CassetteError as error:
            items.append({"file": path.name, "error": str(error)[:300]})
    return items


@router.post("/api/suites/validate")
def validate_suite(body: SuiteRequest) -> dict:
    try:
        suite = load_suite(_suite_path(body.path))
    except CassetteError as error:
        return {"valid": False, "error": str(error)[:1000]}
    return {"valid": True, "digest": suite.digest, "tasks": [t.model_dump(mode="json") for t in suite.cassette.tasks]}


@router.post("/api/suites")
def create_suite(body: SuiteRequest) -> dict:
    try:
        suite = load_suite(_suite_path(body.path))
    except CassetteError as error:
        raise HTTPException(422, str(error)[:1000]) from error
    project_id = _default_project()
    with session_scope() as session:
        row = session.scalar(select(Suite).where(Suite.digest == suite.digest))
        if row is None:
            row = Suite(
                project_id=project_id,
                name=suite.cassette.suite.name,
                schema_version=suite.cassette.schema_version,
                digest=suite.digest,
                source_type="bundled",
                source_revision=str(suite.source_path),
                case_count=len(suite.cassette.tasks),
                definition_json=suite.cassette.model_dump(mode="json"),
            )
            session.add(row)
            session.flush()
        return {"id": row.id, "digest": row.digest, "name": row.name, "case_count": row.case_count}


@router.get("/api/suites/{suite_id}")
def get_suite(suite_id: str) -> dict:
    with session_scope() as session:
        row = session.get(Suite, suite_id)
        if row is None:
            raise HTTPException(404, "suite not found")
        return {
            "id": row.id,
            "digest": row.digest,
            "name": row.name,
            "case_count": row.case_count,
            "definition": row.definition_json,
        }


class LaneBody(BaseModel):
    provider: str
    model: str
    temperature: float | None = 0.0
    seed: int | None = 7
    max_tokens: int | None = 2048


class ExperimentBody(BaseModel):
    suite_id: str
    baseline: LaneBody
    candidate: LaneBody
    policy: MigrationPolicy = Field(default_factory=MigrationPolicy)
    task_ids: list[str] = Field(default_factory=list)
    pull_request_url: str | None = None
    confirm_budget: bool = False


class AutopilotBody(BaseModel):
    suite_id: str
    brief: str = Field(min_length=3, max_length=1000)
    baseline: LaneBody
    candidate: LaneBody
    pull_request_url: str | None = None


def _mission_plan(suite, brief: str) -> tuple[list[str], MigrationPolicy, dict]:
    """Translate one human goal into a bounded, explainable execution plan.

    Task selection is deliberately deterministic: the mission controller may choose from the
    signed cassette, but it cannot invent tasks, graders, tools, or policy fields.
    """

    text = brief.lower()
    category_terms = {
        "bug_fix": ("bug", "repair", "fix", "production"),
        "tool_use": ("tool", "command"),
        "navigation": ("find", "locate", "navigation", "repository"),
        "test_generation": ("test", "coverage"),
        "refactor": ("refactor", "maintain", "cleanup"),
        "recovery": ("recover", "failure", "resilien"),
    }
    categories = {category for category, terms in category_terms.items() if any(term in text for term in terms)}
    critical_only = any(term in text for term in ("critical", "release", "production"))
    all_tasks = list(suite.cassette.tasks)
    if any(term in text for term in ("all", "full", "every", "entire", "complete")):
        selected = all_tasks
    else:
        selected = [
            task
            for task in all_tasks
            if (not critical_only or task.critical) and (not categories or task.category in categories)
        ]
        if not selected:
            selected = [task for task in all_tasks if task.critical] or all_tasks

    strict = any(term in text for term in ("strict", "no regression", "zero regression"))
    policy = MigrationPolicy(
        max_pass_rate_drop=0 if strict else 0.02,
        critical_tasks_must_pass="allow critical" not in text,
        max_p95_latency_ms=15000,
        require_lower_cost_per_success=any(term in text for term in ("cost", "cheaper", "efficient")),
        max_provider_error_rate=0.02,
    )
    plan = {
        "brief": brief,
        "task_ids": [task.id for task in selected],
        "task_count": len(selected),
        "categories": sorted({task.category for task in selected}),
        "critical_tasks": [task.id for task in selected if task.critical],
        "reason": "full workload requested"
        if len(selected) == len(all_tasks)
        else "matched the goal to signed cassette tasks",
        "policy": policy.model_dump(),
    }
    return plan["task_ids"], policy, plan


def _loaded_suite(suite_id: str):
    with session_scope() as session:
        row = session.get(Suite, suite_id)
        if row is None:
            raise HTTPException(404, "suite not found")
        source = row.source_revision
    return load_suite(source)


@router.post("/api/experiments/estimate")
def estimate(body: ExperimentBody) -> dict:
    suite = _loaded_suite(body.suite_id)
    return orchestrator.estimate(suite, body.task_ids or None)


async def _allowed_lane(lane: LaneBody, *, require_nvidia: bool = False) -> None:
    if lane.provider not in ("fixture", "nebius", "benchtrace", "local"):
        raise HTTPException(422, f"unsupported provider {lane.provider!r}")
    if lane.provider == "local" and lane.model not in {
        name.strip() for name in os.environ.get("REPLAYFORGE_LOCAL_MODELS", "").split(",") if name.strip()
    }:
        raise HTTPException(422, "local model must be listed in REPLAYFORGE_LOCAL_MODELS")
    if lane.provider == "local":
        try:
            local_base_url()
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    if lane.provider == "fixture" and lane.model not in FIXTURE_PROFILES:
        raise HTTPException(422, "unknown fixture profile")
    if lane.provider == "nebius":
        provider = NebiusTokenFactoryProvider()
        if not provider.configured:
            raise HTTPException(422, "NEBIUS_TOKEN_FACTORY_API_KEY is required for a live Nebius lane")
        try:
            catalog = await provider.list_models()
        except Exception as error:  # noqa: BLE001 - provider failure is returned without credentials
            raise HTTPException(502, f"could not validate the Nebius model catalog: {str(error)[:240]}") from error
        finally:
            await provider.aclose()
        selected = next((model for model in catalog.models if model.id == lane.model), None)
        if selected is None:
            raise HTTPException(422, "the selected model is not present in the live Nebius catalog")
        if require_nvidia and not selected.is_nvidia:
            raise HTTPException(422, "the candidate lane must use an NVIDIA model from the live Nebius catalog")


@router.post("/api/experiments")
async def create_experiment(body: ExperimentBody, idempotency_key: str | None = Header(default=None)) -> dict:
    if idempotency_key:
        with session_scope() as session:
            existing = session.scalar(select(Experiment).where(Experiment.idempotency_key == idempotency_key))
            if existing:
                return experiment_snapshot(existing.id)
    await _allowed_lane(body.baseline)
    await _allowed_lane(body.candidate, require_nvidia=body.candidate.provider == "nebius")
    suite = _loaded_suite(body.suite_id)
    budget = orchestrator.estimate(suite, body.task_ids or None)
    if not budget["within_budget"] and not body.confirm_budget:
        raise HTTPException(
            409, {"message": "estimate exceeds the configured budget; confirm to continue", "estimate": budget}
        )
    if body.pull_request_url:
        try:
            parse_pr_url(body.pull_request_url)
        except GitHubError as error:
            raise HTTPException(422, str(error)) from error
    with session_scope() as session:
        experiment = Experiment(
            project_id=_default_project(),
            suite_id=body.suite_id,
            status="ready",
            baseline_config_json=body.baseline.model_dump(),
            candidate_config_json=body.candidate.model_dump(),
            policy_json=body.policy.model_dump(),
            budget_json=budget,
            task_ids_json=body.task_ids,
            git_sha=git_revision(suite.fixture_path),
            pull_request_url=body.pull_request_url,
            idempotency_key=idempotency_key,
            fixture_mode="fixture" in (body.baseline.provider, body.candidate.provider),
        )
        session.add(experiment)
        session.flush()
        experiment_id = experiment.id
    bus.publish(
        experiment_id,
        "experiment.created",
        {"suite_digest": suite.digest, "fixture_mode": "fixture" in (body.baseline.provider, body.candidate.provider)},
        actor_type="user",
    )
    bus.publish(
        experiment_id, "experiment.validated", {"estimate": budget}, actor_type="agent", actor_id="experiment-manager"
    )
    return experiment_snapshot(experiment_id)


@router.post("/api/experiments/autopilot")
async def launch_autopilot(body: AutopilotBody, idempotency_key: str | None = Header(default=None)) -> dict:
    """Plan, validate, create, and start a complete evaluation from one goal."""

    suite = _loaded_suite(body.suite_id)
    task_ids, policy, plan = _mission_plan(suite, body.brief)
    created = await create_experiment(
        ExperimentBody(
            suite_id=body.suite_id,
            baseline=body.baseline,
            candidate=body.candidate,
            policy=policy,
            task_ids=task_ids,
            pull_request_url=body.pull_request_url,
        ),
        idempotency_key,
    )
    experiment_id = created["id"]
    bus.publish(
        experiment_id,
        "mission.planned",
        plan,
        actor_type="agent",
        actor_id="mission-controller",
    )
    orchestrator.start(experiment_id)
    return {"experiment": experiment_snapshot(experiment_id), "plan": plan}


@router.get("/api/experiments")
def list_experiments() -> list[dict]:
    with session_scope() as session:
        rows = session.scalars(select(Experiment).order_by(Experiment.created_at.desc()).limit(50)).all()
        out = []
        for row in rows:
            decision = session.scalar(select(ReleaseDecision).where(ReleaseDecision.experiment_id == row.id))
            out.append(
                {
                    "id": row.id,
                    "status": row.status,
                    "created_at": row.created_at.isoformat(),
                    "fixture_mode": row.fixture_mode,
                    "baseline": row.baseline_config_json,
                    "candidate": row.candidate_config_json,
                    "outcome": decision.outcome if decision else None,
                }
            )
        return out


def experiment_snapshot(experiment_id: str) -> dict:
    with session_scope() as session:
        experiment = session.get(Experiment, experiment_id)
        if experiment is None:
            raise HTTPException(404, "experiment not found")
        suite = session.get(Suite, experiment.suite_id)
        runs = session.scalars(select(CaseRun).where(CaseRun.experiment_id == experiment_id)).all()
        pairs = session.scalars(select(PairComparison).where(PairComparison.experiment_id == experiment_id)).all()
        investigations = (
            {
                i.pair_comparison_id: i
                for i in session.scalars(
                    select(Investigation).where(Investigation.pair_comparison_id.in_([p.id for p in pairs]))
                )
            }
            if pairs
            else {}
        )
        metrics = session.scalars(select(Metric).where(Metric.experiment_id == experiment_id)).all()
        decision = session.scalar(select(ReleaseDecision).where(ReleaseDecision.experiment_id == experiment_id))
        mission_event = session.scalar(
            select(Event)
            .where(Event.experiment_id == experiment_id, Event.type == "mission.planned")
            .order_by(Event.seq.desc())
            .limit(1)
        )
        last_seq = session.scalar(
            select(Event.seq).where(Event.experiment_id == experiment_id).order_by(Event.seq.desc()).limit(1)
        )
        tasks = (suite.definition_json or {}).get("tasks", []) if suite else []
        selected = set(experiment.task_ids_json or []) or {t["id"] for t in tasks}
        return {
            "id": experiment.id,
            "status": experiment.status,
            "fixture_mode": experiment.fixture_mode,
            "error": experiment.error,
            "created_at": experiment.created_at.isoformat(),
            "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
            "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
            "suite": {"id": suite.id, "name": suite.name, "digest": suite.digest} if suite else None,
            "baseline": experiment.baseline_config_json,
            "candidate": experiment.candidate_config_json,
            "policy": experiment.policy_json,
            "budget": experiment.budget_json,
            "git_sha": experiment.git_sha,
            "pull_request_url": experiment.pull_request_url,
            "mission_plan": mission_event.payload_json if mission_event else None,
            "tasks": [
                {
                    "id": t["id"],
                    "category": t["category"],
                    "critical": t.get("critical", False),
                    "description": t["description"],
                }
                for t in tasks
                if t["id"] in selected
            ],
            "runs": [
                {
                    "id": r.id,
                    "task_id": r.task_id,
                    "lane": r.lane,
                    "status": r.status,
                    "passed": r.passed,
                    "provider": r.provider,
                    "model": r.model,
                    "latency_ms": r.latency_ms,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "provider_cost": r.provider_cost,
                    "failure_mode": r.failure_mode,
                }
                for r in runs
            ],
            "pairs": [
                {
                    "id": p.id,
                    "task_id": p.task_id,
                    "critical": p.critical,
                    "outcome": p.outcome,
                    "baseline_run_id": p.baseline_run_id,
                    "candidate_run_id": p.candidate_run_id,
                    "trajectory_delta": p.trajectory_delta_json,
                    "investigation": (
                        {
                            "category": investigations[p.id].category,
                            "confidence": investigations[p.id].confidence,
                            "summary": investigations[p.id].summary,
                            "evidence_refs": investigations[p.id].evidence_refs_json,
                            "method": investigations[p.id].method,
                        }
                        if p.id in investigations
                        else None
                    ),
                }
                for p in pairs
            ],
            "metrics": [
                {
                    "lane": m.lane,
                    "name": m.name,
                    "value": m.value,
                    "unit": m.unit,
                    "measurement_kind": m.measurement_kind,
                    "sample_count": m.sample_count,
                    "source": m.source,
                    "detail": m.detail_json,
                }
                for m in metrics
            ],
            "comparison": experiment.comparison_json,
            "decision": (
                {
                    "outcome": decision.outcome,
                    "violations": decision.violations_json,
                    "summary": decision.summary,
                    "policy_version": decision.policy_version,
                    "delivery_status": decision.delivery_status,
                    "delivery_error": decision.delivery_error,
                    "github_check_url": decision.github_check_url,
                }
                if decision
                else None
            ),
            "last_event_seq": last_seq or 0,
        }


@router.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id: str) -> dict:
    return experiment_snapshot(experiment_id)


@router.post("/api/experiments/{experiment_id}/start")
async def start_experiment(experiment_id: str) -> dict:
    snapshot = experiment_snapshot(experiment_id)
    if snapshot["status"] not in ("ready", "running"):
        raise HTTPException(409, f"experiment is {snapshot['status']}")
    orchestrator.start(experiment_id)
    await asyncio.sleep(0)
    return {"started": True, "id": experiment_id}


@router.post("/api/experiments/{experiment_id}/cancel")
def cancel_experiment(experiment_id: str) -> dict:
    return {"cancelled": orchestrator.cancel(experiment_id)}


@router.get("/api/experiments/{experiment_id}/events")
async def events(
    experiment_id: str, request: Request, last_event_id: str | None = Header(default=None), after: int | None = None
) -> EventSourceResponse:
    cursor = after if after is not None else int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def stream():
        nonlocal cursor
        while True:
            if await request.is_disconnected():
                return
            signal = bus.signal_for(experiment_id)
            with session_scope() as session:
                rows = session.scalars(
                    select(Event)
                    .where(Event.experiment_id == experiment_id, Event.seq > cursor)
                    .order_by(Event.seq)
                    .limit(500)
                ).all()
                batch = [serialize(r) for r in rows]
            for item in batch:
                cursor = item["seq"]
                yield {"id": str(item["seq"]), "event": "replayforge", "data": json.dumps(item)}
            if not batch:
                try:
                    await asyncio.wait_for(signal.wait(), timeout=15)
                except TimeoutError:
                    yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(stream())


@router.get("/api/experiments/{experiment_id}/event-log")
def event_log(experiment_id: str, after: int = 0) -> list[dict]:
    with session_scope() as session:
        rows = session.scalars(
            select(Event).where(Event.experiment_id == experiment_id, Event.seq > after).order_by(Event.seq)
        ).all()
        return [serialize(r) for r in rows]


@router.get("/api/experiments/{experiment_id}/comparisons")
def comparisons(experiment_id: str) -> list[dict]:
    return experiment_snapshot(experiment_id)["pairs"]


@router.get("/api/runs/{run_id}/trace")
def run_trace(run_id: str) -> dict:
    with session_scope() as session:
        run = session.get(CaseRun, run_id)
        if run is None:
            raise HTTPException(404, "run not found")
        steps = session.scalars(
            select(ToolStep).where(ToolStep.case_run_id == run_id).order_by(ToolStep.sequence)
        ).all()
        grades = session.scalars(select(Grade).where(Grade.case_run_id == run_id)).all()
        calls = run.trace_json.get("model_calls", [])
        return {
            "id": run.id,
            "task_id": run.task_id,
            "lane": run.lane,
            "provider": run.provider,
            "model": run.model,
            "status": run.status,
            "passed": run.passed,
            "failure": run.trace_json.get("failure"),
            "finish_summary": run.finish_summary,
            "latency_ms": run.latency_ms,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "provider_cost": run.provider_cost,
            "provider_response_ids": run.trace_json.get("metadata", {}).get("provider_response_ids", []),
            "model_calls": [
                {
                    "latency_ms": c.get("latency_ms"),
                    "usage": c.get("usage"),
                    "attempts": c.get("attempts"),
                    "finish_reason": (c.get("response") or {}).get("finish_reason"),
                    "content": ((c.get("response") or {}).get("content") or "")[:2000],
                }
                for c in calls
            ],
            "steps": [
                {
                    "sequence": s.sequence,
                    "tool": s.tool_name,
                    "arguments": s.arguments_json,
                    "ok": s.ok,
                    "error_kind": s.error_kind,
                    "exit_code": s.exit_code,
                    "duration_ms": s.duration_ms,
                    "observation": s.observation_json,
                }
                for s in steps
            ],
            "grades": [
                {
                    "grader": g.grader_type,
                    "version": g.grader_version,
                    "passed": g.passed,
                    "reason": g.reason,
                    "evidence": g.evidence_json,
                }
                for g in grades
            ],
        }


@router.get("/api/runs/{run_id}/artifacts")
def run_artifacts(run_id: str) -> dict:
    trace = run_trace(run_id)
    changed = sorted({f for s in trace["steps"] for f in (s["observation"].get("changed_files") or [])})
    commands = [s for s in trace["steps"] if s["tool"] == "run_command"]
    return {"changed_files": changed, "commands": commands, "grades": trace["grades"]}


@router.get("/api/experiments/{experiment_id}/report.md", response_class=PlainTextResponse)
def report(experiment_id: str) -> str:
    snap = experiment_snapshot(experiment_id)
    if not snap["decision"]:
        raise HTTPException(409, "experiment has no decision yet")
    pairs = [
        {
            "task_id": p["task_id"],
            "critical": p["critical"],
            "baseline_passed": p["outcome"] in ("both_pass", "candidate_regressed"),
            "candidate_passed": p["outcome"] in ("both_pass", "candidate_improved"),
            "finding": p["investigation"],
        }
        for p in snap["pairs"]
    ]
    return render_markdown(
        title=f"ReplayForge experiment {experiment_id}",
        suite_digest=snap["suite"]["digest"],
        lanes={
            "baseline": f"{snap['baseline']['provider']}:{snap['baseline']['model']}",
            "candidate": f"{snap['candidate']['provider']}:{snap['candidate']['model']}",
        },
        pairs=pairs,
        metrics=snap["metrics"],
        comparison=snap["comparison"],
        decision={**snap["decision"], "violations": snap["decision"]["violations"]},
        fixture_mode=snap["fixture_mode"],
        source_revision=snap["git_sha"],
    )


@router.get("/api/experiments/{experiment_id}/report.pdf")
def report_pdf(experiment_id: str) -> Response:
    snap = experiment_snapshot(experiment_id)
    if not snap["decision"]:
        raise HTTPException(409, "experiment has no decision yet")
    content = render_pdf(snap, experiment_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="replayforge-{experiment_id}.pdf"'},
    )


class PublishBody(BaseModel):
    pull_request_url: str | None = None


@router.post("/api/experiments/{experiment_id}/publish-github")
async def publish_github(experiment_id: str, body: PublishBody) -> dict:
    snap = experiment_snapshot(experiment_id)
    decision = snap["decision"]
    if not decision:
        raise HTTPException(409, "experiment has no decision yet")
    url = body.pull_request_url or snap["pull_request_url"]
    if not url:
        raise HTTPException(422, "a pull request URL is required")
    settings = get_settings()
    bus.publish(
        experiment_id, "github.delivery.started", {"pull_request_url": url}, actor_type="agent", actor_id="release-gate"
    )
    try:
        ref = parse_pr_url(url)
        client = GitHubClient(settings.github_token)
        try:
            head = await client.pull_request_head(ref)
            prefix = "[FIXTURE] " if snap["fixture_mode"] else ""
            payload = check_run_payload(
                head_sha=head,
                outcome=decision["outcome"],
                title=f"{prefix}{decision['outcome'].upper()}: {decision['summary'][:180]}",
                summary=report(experiment_id),
                details_url=f"{settings.public_base_url}/experiments/{experiment_id}",
                external_id=f"replayforge-{experiment_id}",
            )
            check = await client.upsert_check_run(ref, payload)
        finally:
            await client.aclose()
    except GitHubError as error:
        with session_scope() as session:
            row = session.scalar(select(ReleaseDecision).where(ReleaseDecision.experiment_id == experiment_id))
            if row:
                row.delivery_status, row.delivery_error = "failed", str(error)[:500]
        bus.publish(
            experiment_id,
            "github.delivery.failed",
            {"error": str(error)[:500]},
            actor_type="agent",
            actor_id="release-gate",
        )
        raise HTTPException(502, str(error)) from error
    with session_scope() as session:
        row = session.scalar(select(ReleaseDecision).where(ReleaseDecision.experiment_id == experiment_id))
        if row:
            row.github_check_id, row.github_check_url = str(check.get("id")), check.get("html_url")
            row.delivery_status, row.delivery_error, row.delivered_at = "delivered", None, datetime.now(UTC)
    bus.publish(
        experiment_id,
        "github.delivery.completed",
        {"check_url": check.get("html_url")},
        actor_type="agent",
        actor_id="release-gate",
    )
    return {"delivered": True, "check_url": check.get("html_url")}


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> dict:
    body = await request.body()
    if not verify_signature(get_settings().github_webhook_secret, body, x_hub_signature_256):
        raise HTTPException(401, "invalid signature")
    if not x_github_delivery:
        raise HTTPException(400, "missing delivery id")
    with session_scope() as session:
        if session.get(WebhookDelivery, x_github_delivery):
            return {"duplicate": True}
        session.add(WebhookDelivery(delivery_id=x_github_delivery, event=x_github_event or "unknown"))
    return {"accepted": True, "event": x_github_event}
