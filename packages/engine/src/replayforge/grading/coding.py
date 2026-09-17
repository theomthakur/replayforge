"""Deterministic coding graders. Tests outrank opinions; no grader calls a model."""

from __future__ import annotations

import re

from benchtrace.trace import GraderOutput, JsonValue

from replayforge.cassettes.schema import GraderSpec, TaskSpec
from replayforge.orchestration.agent import AgentRun
from replayforge.sandbox.local import LocalSandbox

GRADER_VERSION = "rf-graders-1"
_PYTEST_SUMMARY = re.compile(r"(\d+) (passed|failed|error|errors)")


def _output(name: str, passed: bool, reason: str, evidence: dict[str, JsonValue]) -> GraderOutput:
    return GraderOutput(
        grader=name,
        score=1.0 if passed else 0.0,
        reason=reason,
        metadata={"version": GRADER_VERSION, "evidence": evidence},
    )


def _pytest_counts(text: str) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "errors": 0}
    for number, kind in _PYTEST_SUMMARY.findall(text):
        key = "errors" if kind.startswith("error") else kind
        counts[key] += int(number)
    return counts


async def grade_case(
    task: TaskSpec,
    run: AgentRun,
    sandbox: LocalSandbox,
    baseline_snapshot: dict[str, str],
    timeout_seconds: float,
) -> list[GraderOutput]:
    after = sandbox.snapshot()
    changed = sorted(k for k in set(baseline_snapshot) | set(after) if baseline_snapshot.get(k) != after.get(k))
    results: list[GraderOutput] = []
    for spec in task.graders:
        results.append(await _grade_one(spec, run, sandbox, changed, timeout_seconds))
    return results


async def _grade_one(
    spec: GraderSpec, run: AgentRun, sandbox: LocalSandbox, changed: list[str], timeout: float
) -> GraderOutput:
    match spec.type:
        case "command":
            result = await sandbox.run(spec.command, timeout)
            ok = result.exit_code == spec.expected_exit_code and not result.timed_out
            tail = (result.stdout + result.stderr).strip().splitlines()[-12:]
            return _output(
                "command",
                ok,
                f"`{spec.command}` exited {result.exit_code} (expected {spec.expected_exit_code})"
                + (" after timeout" if result.timed_out else ""),
                {"command": spec.command, "exit_code": result.exit_code, "output_tail": tail},
            )
        case "test_count":
            result = await sandbox.run(spec.command, timeout)
            counts = _pytest_counts(result.stdout + result.stderr)
            ok = counts["passed"] >= spec.min_passed and counts["failed"] + counts["errors"] <= spec.max_failed
            return _output(
                "test_count",
                ok,
                f"{counts['passed']} passed, {counts['failed']} failed, {counts['errors']} errors "
                f"(need >= {spec.min_passed} passed, <= {spec.max_failed} failing)",
                {"command": spec.command, **counts},
            )
        case "forbidden_paths":
            touched = [
                path
                for path in changed
                if any(
                    path == p.rstrip("/") or path.startswith(p if p.endswith("/") else p + "/") or path == p
                    for p in spec.paths
                )
            ]
            return _output(
                "forbidden_paths",
                not touched,
                "no protected paths changed" if not touched else f"protected paths changed: {', '.join(touched)}",
                {"protected": list(spec.paths), "touched": touched, "changed": changed},
            )
        case "file_exists":
            exists = sandbox.resolve(spec.path).is_file()
            return _output(
                "file_exists",
                exists,
                f"{spec.path} {'exists' if exists else 'is missing'}",
                {"path": spec.path},
            )
        case "file_absent":
            exists = sandbox.resolve(spec.path).exists()
            return _output(
                "file_absent",
                not exists,
                f"{spec.path} {'still exists' if exists else 'is absent'}",
                {"path": spec.path},
            )
        case "file_regex":
            path = sandbox.resolve(spec.path)
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            ok = bool(re.search(spec.pattern, text))
            return _output(
                "file_regex",
                ok,
                f"/{spec.pattern}/ {'found' if ok else 'not found'} in {spec.path}",
                {"path": spec.path, "pattern": spec.pattern},
            )
        case "output_regex":
            summary = run.finish_summary or ""
            ok = bool(re.search(spec.pattern, summary))
            return _output(
                "output_regex",
                ok,
                f"/{spec.pattern}/ {'matched' if ok else 'did not match'} the finish summary",
                {"pattern": spec.pattern, "summary": summary[:500]},
            )
        case "tool_contract":
            used = [s.tool for s in run.steps if s.ok]
            malformed = [s.sequence for s in run.steps if s.error_kind == "malformed_arguments"]
            if spec.ordered:
                position = 0
                for tool in used:
                    if position < len(spec.required_tools) and tool == spec.required_tools[position]:
                        position += 1
                ok = position == len(spec.required_tools)
            else:
                ok = all(tool in used for tool in spec.required_tools)
            return _output(
                "tool_contract",
                ok,
                ("required tools used" + (" in order" if spec.ordered else ""))
                if ok
                else f"required tools {list(spec.required_tools)} not satisfied by successful calls {used}",
                {
                    "required": list(spec.required_tools),
                    "ordered": spec.ordered,
                    "used": used,
                    "malformed_steps": malformed,
                },
            )
    raise ValueError(f"unknown grader {spec.type}")
