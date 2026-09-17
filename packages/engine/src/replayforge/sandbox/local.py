"""Local process sandbox: a disposable fixture copy with scrubbed env and hard limits.

This backend isolates the workspace, environment and process group, and enforces time, CPU,
file-size and output limits. It does not provide kernel-level isolation; use the Docker backend
when available. The README describes ReplayForge as an evaluation prototype, not a secure
code-execution platform.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import shlex
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path

from replayforge.cassettes.schema import is_allowed_command
from replayforge.sandbox.base import CommandResult, PathViolation, SandboxError, SandboxInfo

_MAX_FILE_BYTES = 256_000


def _limit_child() -> None:  # pragma: no cover - runs in the child process
    import resource

    os.setsid()
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_FSIZE, (_MAX_FILE_BYTES * 8, _MAX_FILE_BYTES * 8))


class LocalSandbox:
    """A per-run copy of a fixture directory."""

    def __init__(self, fixture: Path, *, max_output_chars: int = 6000) -> None:
        if not fixture.is_dir():
            raise SandboxError(f"fixture does not exist: {fixture}")
        self._tmp = Path(tempfile.mkdtemp(prefix="replayforge-"))
        self.workspace = (self._tmp / "work").resolve()
        shutil.copytree(fixture, self.workspace, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
        self.max_output_chars = max_output_chars
        self.info = SandboxInfo(
            backend="local",
            workspace=self.workspace,
            network_enabled=False,
            limits={"cpu_seconds": 60, "max_file_bytes": _MAX_FILE_BYTES * 8},
        )

    def resolve(self, relative: str) -> Path:
        """Resolve a workspace-relative path, following symlinks, and reject escapes."""

        if not isinstance(relative, str) or "\0" in relative:
            raise PathViolation("path must be a string")
        candidate = (self.workspace / relative.lstrip("/")).resolve()
        if candidate != self.workspace and self.workspace not in candidate.parents:
            raise PathViolation(f"path escapes the workspace: {relative!r}")
        return candidate

    def relative(self, path: Path) -> str:
        return path.relative_to(self.workspace).as_posix()

    async def run(self, command: str, timeout_seconds: float) -> CommandResult:
        if not is_allowed_command(command):
            raise SandboxError(f"command not allowed: {command!r}")
        argv = shlex.split(command)
        if argv[0] == "python":
            argv[0] = sys.executable
        env = {
            "PATH": os.path.dirname(sys.executable) + ":/usr/bin:/bin",
            "HOME": str(self._tmp),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "LANG": "C.UTF-8",
            "NO_PROXY": "*",
            "http_proxy": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
        }
        started = time.perf_counter()
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=self.workspace,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=_limit_child,
        )
        timed_out = False
        try:
            out, err = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            timed_out = True
            self._kill_group(process.pid)
            out, err = await process.communicate()
        duration = (time.perf_counter() - started) * 1000.0
        stdout, t1 = self._clip(out.decode(errors="replace"))
        stderr, t2 = self._clip(err.decode(errors="replace"))
        return CommandResult(
            command=command,
            exit_code=process.returncode if process.returncode is not None else -1,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration,
            timed_out=timed_out,
            truncated=t1 or t2,
        )

    @staticmethod
    def _kill_group(pid: int) -> None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGKILL)

    def _clip(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.max_output_chars:
            return text, False
        return text[: self.max_output_chars] + "\n...[output truncated]", True

    def snapshot(self) -> dict[str, str]:
        """Content hashes of every workspace file, used for protected-path checks."""

        hashes: dict[str, str] = {}
        for file in sorted(self.workspace.rglob("*")):
            if not file.is_file() or "__pycache__" in file.parts or file.suffix == ".pyc":
                continue
            hashes[self.relative(file)] = hashlib.sha256(file.read_bytes()).hexdigest()
        return hashes

    def close(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)
