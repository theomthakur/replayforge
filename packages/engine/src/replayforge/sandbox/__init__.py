"""Sandbox backends."""

from pathlib import Path

from replayforge.sandbox.base import (
    CommandResult,
    PathViolation,
    Sandbox,
    SandboxError,
    SandboxInfo,
)
from replayforge.sandbox.local import LocalSandbox


def create_sandbox(fixture: Path, backend: str = "local", **kwargs: int) -> LocalSandbox:
    if backend == "docker":
        from replayforge.sandbox.docker import DockerSandbox

        return DockerSandbox(fixture, **kwargs)
    if backend != "local":
        raise SandboxError(f"unknown sandbox backend {backend!r}")
    return LocalSandbox(fixture, **kwargs)


__all__ = [
    "CommandResult",
    "LocalSandbox",
    "PathViolation",
    "Sandbox",
    "SandboxError",
    "SandboxInfo",
    "create_sandbox",
]
