"""Cassette schema, safety validation and immutable suite digests."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

CASSETTE_SCHEMA_VERSION: Literal["1.0"] = "1.0"

TOOL_NAMES = ("read_file", "list_files", "search_text", "apply_patch", "run_command", "finish")
ToolName = Literal["read_file", "list_files", "search_text", "apply_patch", "run_command", "finish"]

# Commands a grader or agent may run inside a sandbox. Anything else is rejected before a run.
ALLOWED_COMMAND_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("python", "-m", "pytest"),
    ("python", "-m", "py_compile"),
)

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


class CassetteError(ValueError):
    """A cassette failed schema or safety validation."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Limits(_Model):
    max_steps: int = Field(default=12, ge=1, le=60)
    max_wall_seconds: int = Field(default=120, ge=5, le=900)
    max_tool_output_chars: int = Field(default=6000, ge=500, le=50_000)


class CommandGraderSpec(_Model):
    type: Literal["command"]
    command: str
    expected_exit_code: int = 0


class TestCountGraderSpec(_Model):
    type: Literal["test_count"]
    command: str
    min_passed: int = Field(ge=0)
    max_failed: int = Field(default=0, ge=0)


class ForbiddenPathsGraderSpec(_Model):
    type: Literal["forbidden_paths"]
    paths: list[str] = Field(min_length=1)


class FileExistsGraderSpec(_Model):
    type: Literal["file_exists"]
    path: str


class FileAbsentGraderSpec(_Model):
    type: Literal["file_absent"]
    path: str


class FileRegexGraderSpec(_Model):
    type: Literal["file_regex"]
    path: str
    pattern: str


class OutputRegexGraderSpec(_Model):
    type: Literal["output_regex"]
    pattern: str


class ToolContractGraderSpec(_Model):
    type: Literal["tool_contract"]
    required_tools: list[ToolName] = Field(min_length=1)
    ordered: bool = False


GraderSpec = Annotated[
    CommandGraderSpec
    | TestCountGraderSpec
    | ForbiddenPathsGraderSpec
    | FileExistsGraderSpec
    | FileAbsentGraderSpec
    | FileRegexGraderSpec
    | OutputRegexGraderSpec
    | ToolContractGraderSpec,
    Field(discriminator="type"),
]


class TaskSpec(_Model):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]{1,62}$")
    category: Literal["bug_fix", "tool_use", "navigation", "test_generation", "refactor", "recovery"]
    description: str
    critical: bool = False
    prompt: str = Field(min_length=10)
    tools: list[ToolName] = Field(default_factory=lambda: list(TOOL_NAMES))
    limits: Limits | None = None
    graders: list[GraderSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def finish_available(self) -> TaskSpec:
        if "finish" not in self.tools:
            raise ValueError(f"task {self.id!r} must expose the finish tool")
        return self


class SuiteHeader(_Model):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]{1,62}$")
    name: str
    description: str = ""
    repository_fixture: str
    setup_command: str | None = None
    default_timeout_seconds: int = Field(default=90, ge=5, le=900)
    default_limits: Limits = Field(default_factory=Limits)


class Cassette(_Model):
    schema_version: Literal["1.0"]
    suite: SuiteHeader
    tasks: list[TaskSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_task_ids(self) -> Cassette:
        seen: set[str] = set()
        for task in self.tasks:
            if task.id in seen:
                raise ValueError(f"duplicate task id {task.id!r}")
            seen.add(task.id)
        return self

    def limits_for(self, task: TaskSpec) -> Limits:
        return task.limits or self.suite.default_limits

    def task(self, task_id: str) -> TaskSpec:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(task_id)


@dataclass(frozen=True, slots=True)
class LoadedSuite:
    """A validated cassette plus its resolved fixture path and immutable digest."""

    cassette: Cassette
    source_path: Path
    fixture_path: Path
    digest: str


def is_allowed_command(command: str) -> bool:
    """Return True when a command matches an allowlisted prefix and has no shell syntax."""

    if any(token in command for token in (";", "&&", "||", "|", "`", "$(", ">", "<", "\n")):
        return False
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return any(tuple(parts[: len(prefix)]) == prefix for prefix in ALLOWED_COMMAND_PREFIXES)


def _check_relative_path(path: str, field: str) -> None:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise CassetteError(f"{field}: path {path!r} must be relative and stay inside the repository")


def _check_safety(cassette: Cassette) -> None:
    texts = [cassette.suite.description] + [t.prompt for t in cassette.tasks]
    for text in texts:
        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                raise CassetteError("cassette text contains a value that looks like a secret")
    if cassette.suite.setup_command and not is_allowed_command(cassette.suite.setup_command):
        raise CassetteError(f"setup_command is not allowlisted: {cassette.suite.setup_command!r}")
    for task in cassette.tasks:
        for grader in task.graders:
            if grader.type in ("command", "test_count") and not is_allowed_command(grader.command):
                raise CassetteError(f"{task.id}: grader command not allowlisted: {grader.command!r}")
            if grader.type == "forbidden_paths":
                for path in grader.paths:
                    _check_relative_path(path, f"{task.id}.forbidden_paths")
            if grader.type in ("file_exists", "file_absent", "file_regex"):
                _check_relative_path(grader.path, f"{task.id}.{grader.type}")
            if grader.type in ("file_regex", "output_regex"):
                try:
                    re.compile(grader.pattern)
                except re.error as error:
                    raise CassetteError(f"{task.id}: invalid regex {grader.pattern!r}: {error}") from error


def _fixture_digest(fixture: Path) -> str:
    hasher = hashlib.sha256()
    for file in sorted(p for p in fixture.rglob("*") if p.is_file()):
        relative = file.relative_to(fixture).as_posix()
        if "__pycache__" in relative or relative.endswith(".pyc"):
            continue
        hasher.update(relative.encode())
        hasher.update(b"\0")
        hasher.update(file.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def suite_digest(cassette: Cassette, fixture: Path) -> str:
    """Hash the canonical cassette definition together with every fixture file."""

    canonical = json.dumps(cassette.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    hasher = hashlib.sha256()
    hasher.update(canonical.encode())
    hasher.update(_fixture_digest(fixture).encode())
    return "sha256:" + hasher.hexdigest()


def parse_cassette(raw: object) -> Cassette:
    try:
        cassette = Cassette.model_validate(raw)
    except ValidationError as error:
        raise CassetteError(str(error)) from error
    _check_safety(cassette)
    return cassette


def load_suite(path: str | Path, *, root: str | Path | None = None) -> LoadedSuite:
    """Load, validate and hash a cassette file. Fixture paths resolve against ``root``."""

    source = Path(path).resolve()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise CassetteError(f"cannot read cassette {source}: {error}") from error
    cassette = parse_cassette(raw)
    _check_relative_path(cassette.suite.repository_fixture, "suite.repository_fixture")
    base = Path(root).resolve() if root else _find_root(source)
    fixture = (base / cassette.suite.repository_fixture).resolve()
    if not fixture.is_dir() or base not in fixture.parents:
        raise CassetteError(f"repository fixture not found inside {base}: {cassette.suite.repository_fixture}")
    return LoadedSuite(
        cassette=cassette,
        source_path=source,
        fixture_path=fixture,
        digest=suite_digest(cassette, fixture),
    )


def _find_root(source: Path) -> Path:
    for parent in source.parents:
        if (parent / "fixtures").is_dir():
            return parent
    return source.parent
