"""SQLAlchemy models and session management. The database is authoritative; SSE is transport only."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from replayforge_api.config import get_settings


def _id() -> str:
    return uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict: JSON, list: JSON}


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(200))
    github_owner: Mapped[str | None] = mapped_column(String(100))
    github_repo: Mapped[str | None] = mapped_column(String(100))
    default_branch: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Suite(Base):
    __tablename__ = "suites"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(200))
    schema_version: Mapped[str] = mapped_column(String(10))
    digest: Mapped[str] = mapped_column(String(80), index=True)
    source_type: Mapped[str] = mapped_column(String(20))
    source_revision: Mapped[str] = mapped_column(Text)
    case_count: Mapped[int] = mapped_column(Integer)
    definition_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    suite_id: Mapped[str] = mapped_column(ForeignKey("suites.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    baseline_config_json: Mapped[dict] = mapped_column(JSON)
    candidate_config_json: Mapped[dict] = mapped_column(JSON)
    policy_json: Mapped[dict] = mapped_column(JSON)
    budget_json: Mapped[dict] = mapped_column(JSON)
    task_ids_json: Mapped[list] = mapped_column(JSON)
    git_sha: Mapped[str | None] = mapped_column(String(64))
    pull_request_url: Mapped[str | None] = mapped_column(String(300))
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True)
    fixture_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    comparison_json: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(100), default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseRun(Base):
    __tablename__ = "case_runs"
    __table_args__ = (UniqueConstraint("experiment_id", "task_id", "case_id", "repeat_index", "lane"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(80))
    case_id: Mapped[str] = mapped_column(String(80), default="default")
    repeat_index: Mapped[int] = mapped_column(Integer, default=0)
    lane: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(200))
    model_revision: Mapped[str | None] = mapped_column(String(100))
    seed: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    provider_cost: Mapped[float | None] = mapped_column(Float)
    failure_mode: Mapped[str | None] = mapped_column(String(40))
    finish_summary: Mapped[str | None] = mapped_column(Text)
    grader_version: Mapped[str] = mapped_column(String(40))
    trace_json: Mapped[dict] = mapped_column(JSON)


class ToolStep(Base):
    __tablename__ = "tool_steps"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    case_run_id: Mapped[str] = mapped_column(ForeignKey("case_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    tool_name: Mapped[str] = mapped_column(String(40))
    arguments_json: Mapped[dict] = mapped_column(JSON)
    observation_json: Mapped[dict] = mapped_column(JSON)
    ok: Mapped[bool] = mapped_column(Boolean)
    error_kind: Mapped[str | None] = mapped_column(String(40))
    exit_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Grade(Base):
    __tablename__ = "grades"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    case_run_id: Mapped[str] = mapped_column(ForeignKey("case_runs.id"), index=True)
    grader_type: Mapped[str] = mapped_column(String(40))
    grader_version: Mapped[str] = mapped_column(String(40))
    score: Mapped[float] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PairComparison(Base):
    __tablename__ = "pair_comparisons"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    task_id: Mapped[str] = mapped_column(String(80))
    case_id: Mapped[str] = mapped_column(String(80), default="default")
    repeat_index: Mapped[int] = mapped_column(Integer, default=0)
    critical: Mapped[bool] = mapped_column(Boolean, default=False)
    baseline_run_id: Mapped[str] = mapped_column(ForeignKey("case_runs.id"))
    candidate_run_id: Mapped[str] = mapped_column(ForeignKey("case_runs.id"))
    outcome: Mapped[str] = mapped_column(String(30))
    trajectory_delta_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    pair_comparison_id: Mapped[str] = mapped_column(ForeignKey("pair_comparisons.id"), index=True)
    category: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(Text)
    evidence_refs_json: Mapped[list] = mapped_column(JSON)
    method: Mapped[str] = mapped_column(String(10))
    model: Mapped[str | None] = mapped_column(String(200))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Metric(Base):
    __tablename__ = "metrics"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), index=True)
    lane: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(60))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20))
    measurement_kind: Mapped[str] = mapped_column(String(20))
    sample_count: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(200))
    detail_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReleaseDecision(Base):
    __tablename__ = "release_decisions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), unique=True)
    outcome: Mapped[str] = mapped_column(String(10))
    violations_json: Mapped[list] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(String(40))
    github_check_id: Mapped[str | None] = mapped_column(String(40))
    github_check_url: Mapped[str | None] = mapped_column(String(300))
    delivery_status: Mapped[str] = mapped_column(String(20), default="not_requested")
    delivery_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Event(Base):
    __tablename__ = "events"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(32), unique=True, default=_id)
    experiment_id: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(60))
    actor_type: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[str | None] = mapped_column(String(100))
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    delivery_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    event: Mapped[str] = mapped_column(String(60))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


_engine = None
_factory: sessionmaker[Session] | None = None


def init_db(url: str | None = None) -> None:
    global _engine, _factory
    database_url = url or get_settings().database_url
    if database_url.startswith("sqlite:///"):
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(
        database_url, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    Base.metadata.create_all(_engine)
    _factory = sessionmaker(_engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    if _factory is None:
        init_db()
    assert _factory is not None
    session = _factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
