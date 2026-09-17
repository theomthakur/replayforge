"""Sandbox protocol shared by local and container backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class SandboxError(RuntimeError):
    """A sandbox operation was rejected or failed for infrastructure reasons."""


class PathViolation(SandboxError):
    """A requested path escaped the workspace."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    truncated: bool = False


@dataclass(slots=True)
class SandboxInfo:
    backend: str
    workspace: Path
    network_enabled: bool = False
    limits: dict[str, int] = field(default_factory=dict)


class Sandbox(Protocol):
    """A disposable copy of a repository fixture with bounded command execution."""

    info: SandboxInfo

    def resolve(self, relative: str) -> Path: ...

    async def run(self, command: str, timeout_seconds: float) -> CommandResult: ...

    def snapshot(self) -> dict[str, str]: ...

    def close(self) -> None: ...
