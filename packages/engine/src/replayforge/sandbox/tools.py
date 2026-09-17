"""The coding tool contract exposed to agents, with schema validation and execution.

The model never receives host access. Every call is validated against a JSON Schema, authorized
against the task's tool list, executed against the sandbox copy and recorded.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

import jsonschema
from benchtrace.trace import JsonValue, ToolDefinition

from replayforge.redaction import redact
from replayforge.sandbox.base import PathViolation, SandboxError
from replayforge.sandbox.local import LocalSandbox

TOOL_SCHEMAS: dict[str, tuple[str, dict[str, JsonValue]]] = {
    "read_file": (
        "Read a UTF-8 text file from the repository. Optionally restrict to a line range.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to the repository root."},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    ),
    "list_files": (
        "List files and directories under a repository path.",
        {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory relative to the root. Use . for the root.",
                },
                "recursive": {"type": "boolean"},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    ),
    "search_text": (
        "Search repository files for a literal string. Returns matching lines with file and line number.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "path": {
                    "type": "string",
                    "description": "Optional directory to limit the search.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    "apply_patch": (
        "Change files. Either pass `patch`, a unified diff with paths relative to the repository "
        "root, or pass `path` and `content` to replace one file's entire content (creating it if needed).",
        {
            "type": "object",
            "properties": {
                "patch": {"type": "string", "minLength": 1},
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "oneOf": [{"required": ["patch"]}, {"required": ["path", "content"]}],
            "additionalProperties": False,
        },
    ),
    "run_command": (
        "Run an allowlisted command in the repository, for example `python -m pytest -q tests/test_x.py`.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string", "minLength": 1},
                "timeout": {"type": "integer", "minimum": 1, "maximum": 120},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    ),
    "finish": (
        "Finish the task with a short summary of what you found or changed.",
        {
            "type": "object",
            "properties": {"summary": {"type": "string", "minLength": 1}},
            "required": ["summary"],
            "additionalProperties": False,
        },
    ),
}


def tool_definitions(names: Sequence[str]) -> list[ToolDefinition]:
    return [
        ToolDefinition(name=name, description=TOOL_SCHEMAS[name][0], parameters=TOOL_SCHEMAS[name][1]) for name in names
    ]


@dataclass(slots=True)
class ToolOutcome:
    tool: str
    ok: bool
    result: dict[str, JsonValue]
    error_kind: str | None = None  # malformed_arguments | unauthorized_tool | path_violation | tool_error
    exit_code: int | None = None
    duration_ms: float = 0.0
    changed_files: list[str] = field(default_factory=list)


class ToolExecutor:
    def __init__(self, sandbox: LocalSandbox, allowed: Sequence[str], *, max_chars: int = 6000) -> None:
        self.sandbox = sandbox
        self.allowed = set(allowed)
        self.max_chars = max_chars

    async def execute(self, name: str, arguments: dict[str, JsonValue]) -> ToolOutcome:
        started = time.perf_counter()
        if name not in TOOL_SCHEMAS or name not in self.allowed:
            return ToolOutcome(name, False, {"error": f"tool {name!r} is not available"}, "unauthorized_tool")
        try:
            jsonschema.validate(arguments, TOOL_SCHEMAS[name][1])
        except jsonschema.ValidationError as error:
            return ToolOutcome(name, False, {"error": f"invalid arguments: {error.message}"}, "malformed_arguments")
        try:
            outcome = await getattr(self, f"_{name}")(arguments)
        except PathViolation as error:
            outcome = ToolOutcome(name, False, {"error": str(error)}, "path_violation")
        except (SandboxError, OSError, UnicodeDecodeError, ValueError) as error:
            outcome = ToolOutcome(name, False, {"error": redact(str(error))}, "tool_error")
        outcome.duration_ms = (time.perf_counter() - started) * 1000.0
        return outcome

    def _clip(self, text: str) -> str:
        text = redact(text)
        return text if len(text) <= self.max_chars else text[: self.max_chars] + "\n...[truncated]"

    async def _read_file(self, args: dict[str, JsonValue]) -> ToolOutcome:
        path = self.sandbox.resolve(str(args["path"]))
        if not path.is_file():
            return ToolOutcome("read_file", False, {"error": f"not a file: {args['path']}"}, "tool_error")
        lines = path.read_text(encoding="utf-8").splitlines()
        start = int(args.get("start_line", 1))  # type: ignore[arg-type]
        end = int(args.get("end_line", len(lines)))  # type: ignore[arg-type]
        numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(lines[start - 1 : end], start))
        return ToolOutcome("read_file", True, {"path": str(args["path"]), "content": self._clip(numbered)})

    async def _list_files(self, args: dict[str, JsonValue]) -> ToolOutcome:
        root = self.sandbox.resolve(str(args["path"]))
        if not root.is_dir():
            return ToolOutcome("list_files", False, {"error": f"not a directory: {args['path']}"}, "tool_error")
        pattern = root.rglob("*") if args.get("recursive") else root.iterdir()
        entries = sorted(
            self.sandbox.relative(p) + ("/" if p.is_dir() else "")
            for p in pattern
            if "__pycache__" not in p.parts and p.suffix != ".pyc"
        )
        return ToolOutcome("list_files", True, {"entries": entries[:500], "count": len(entries)})

    async def _search_text(self, args: dict[str, JsonValue]) -> ToolOutcome:
        root = self.sandbox.resolve(str(args.get("path", ".")))
        query = str(args["query"])
        matches: list[str] = []
        for file in sorted(root.rglob("*")):
            if not file.is_file() or "__pycache__" in file.parts or file.suffix == ".pyc":
                continue
            try:
                for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
                    if query in line:
                        matches.append(f"{self.sandbox.relative(file)}:{number}: {line.strip()}")
            except UnicodeDecodeError:
                continue
            if len(matches) >= 100:
                break
        return ToolOutcome(
            "search_text",
            True,
            {"matches": [self._clip(m) for m in matches], "count": len(matches)},
        )

    async def _apply_patch(self, args: dict[str, JsonValue]) -> ToolOutcome:
        before = self.sandbox.snapshot()
        if "patch" in args:
            patch = str(args["patch"])
            # Validate ordinary diff headers and metadata-only rename/copy operations. `git apply`
            # remains in its safe default mode; agent-authored patches never need unsafe paths.
            for header in re.findall(
                r"^(?:---|\+\+\+|rename from|rename to|copy from|copy to) (.+)$", patch, flags=re.M
            ):
                header = header.strip().strip('"')
                cleaned = re.sub(r"^[ab]/", "", header)
                if cleaned != "/dev/null":
                    self.sandbox.resolve(cleaned)
            if re.search(r"^(?:new file mode|old mode) 120000$", patch, flags=re.M):
                raise PathViolation("symbolic-link patches are not allowed")
            process = await asyncio.create_subprocess_exec(
                "git",
                "apply",
                "--recount",
                "--whitespace=nowarn",
                "-",
                cwd=self.sandbox.workspace,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await process.communicate(patch.encode())
            if process.returncode != 0:
                return ToolOutcome(
                    "apply_patch",
                    False,
                    {
                        "error": "patch did not apply",
                        "detail": self._clip(err.decode(errors="replace")),
                    },
                    "tool_error",
                )
        else:
            target = self.sandbox.resolve(str(args["path"]))
            content = str(args["content"])
            if len(content.encode()) > 200_000:
                return ToolOutcome("apply_patch", False, {"error": "file content too large"}, "tool_error")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        after = self.sandbox.snapshot()
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        return ToolOutcome("apply_patch", True, {"changed_files": changed}, changed_files=changed)

    async def _run_command(self, args: dict[str, JsonValue]) -> ToolOutcome:
        command = str(args["command"])
        timeout = int(args.get("timeout", 60))  # type: ignore[arg-type]
        try:
            result = await self.sandbox.run(command, timeout)
        except SandboxError as error:
            return ToolOutcome("run_command", False, {"error": str(error)}, "tool_error")
        return ToolOutcome(
            "run_command",
            True,
            {
                "exit_code": result.exit_code,
                "stdout": self._clip(result.stdout),
                "stderr": self._clip(result.stderr),
                "timed_out": result.timed_out,
            },
            exit_code=result.exit_code,
        )

    async def _finish(self, args: dict[str, JsonValue]) -> ToolOutcome:
        return ToolOutcome("finish", True, {"summary": self._clip(str(args["summary"]))})
