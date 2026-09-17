"""Rootless container sandbox backend.

Commands run in a disposable container with networking disabled, an unprivileged user and CPU,
memory and process limits. Only the fixture copy is mounted; the host project and Docker socket are
never mounted. File tools operate on the same copy through the local path guard.

Status: implemented but not yet exercised on this machine (the Docker daemon was not running on
17 September 2026). The local backend is used until this is verified.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import time
from pathlib import Path

from replayforge.cassettes.schema import is_allowed_command
from replayforge.sandbox.base import CommandResult, SandboxError
from replayforge.sandbox.local import LocalSandbox


class DockerSandbox(LocalSandbox):
    def __init__(self, fixture: Path, *, image: str = "python:3.12-slim", **kwargs: int) -> None:
        super().__init__(fixture, **kwargs)
        self.image = image
        self.info.backend = "docker"
        self.info.limits.update({"memory_mb": 512, "pids": 128, "cpus_millis": 1000})

    def _container_identity(self) -> str:
        """Match the host owner without ever running the container as root."""

        uid, gid = os.getuid(), os.getgid()
        if uid != 0:
            return f"{uid}:{gid}"
        # The workspace is an isolated temporary copy. A root API process hands that copy to
        # nobody rather than giving the container root access to a read/write bind mount.
        try:
            for path in (self.workspace, *self.workspace.rglob("*")):
                os.chown(path, 65534, 65534, follow_symlinks=False)
        except OSError as error:
            raise SandboxError("cannot prepare a non-root Docker workspace") from error
        return "65534:65534"

    async def run(self, command: str, timeout_seconds: float) -> CommandResult:
        if not is_allowed_command(command):
            raise SandboxError(f"command not allowed: {command!r}")
        identity = self._container_identity()
        argv = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--user",
            identity,
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "--read-only",
            "--tmpfs",
            "/tmp:size=64m",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "HOME=/tmp",
            "-v",
            f"{self.workspace}:/work:rw",
            "-w",
            "/work",
            self.image,
            *shlex.split(command),
        ]
        started = time.perf_counter()
        process = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        timed_out = False
        try:
            out, err = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            timed_out = True
            process.kill()
            out, err = await process.communicate()
        stdout, t1 = self._clip(out.decode(errors="replace"))
        stderr, t2 = self._clip(err.decode(errors="replace"))
        return CommandResult(
            command=command,
            exit_code=process.returncode if process.returncode is not None else -1,
            stdout=stdout,
            stderr=stderr,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            timed_out=timed_out,
            truncated=t1 or t2,
        )
