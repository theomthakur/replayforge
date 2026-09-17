"""Deterministic fixture provider for tests and the offline demo.

It replays scripted tool calls derived from reference solutions. It is not a model. Every run it
produces is labelled provider ``fixture`` and must never be presented as a model result.

Profiles:
- ``fixture/reference`` follows the reference solution for every task.
- ``fixture/variant`` follows it except on configured tasks, where it sends malformed tool
  arguments or skips verification, so the regression pipeline can be tested end to end.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchtrace.providers.base import Provider, ProviderConfig, WireResult
from benchtrace.trace import TokenUsage, ToolCall, TraceRequest, TraceResponse

from replayforge.cassettes.schema import Cassette, TaskSpec

VARIANT_BREAKS = {"repair-discount": "malformed_arguments", "tool-find-timeout": "wrong_tool"}


class FixtureProvider(Provider):
    name = "fixture"
    supports_seed = True

    def __init__(self, cassette: Cassette, solutions_dir: Path, config: ProviderConfig | None = None) -> None:
        super().__init__(config or ProviderConfig(max_retries=0))
        self.cassette = cassette
        self.solutions = solutions_dir

    def _task_for(self, request: TraceRequest) -> TaskSpec:
        task_id = str(request.case_input.get("task_id", ""))
        return self.cassette.task(task_id)

    def _plan(self, task: TaskSpec, profile: str) -> list[tuple[str, dict[str, object]]]:
        steps: list[tuple[str, dict[str, object]]] = []
        commands = [g.command for g in task.graders if g.type in ("command", "test_count")]
        if task.category == "recovery" and commands:
            steps.append(("run_command", {"command": commands[0]}))
        solution = self.solutions / task.id
        breaks = VARIANT_BREAKS.get(task.id) if profile == "variant" else None
        if solution.is_dir():
            for file in sorted(p for p in solution.rglob("*") if p.is_file()):
                relative = file.relative_to(solution).as_posix()
                if task.category != "test_generation":
                    steps.append(("read_file", {"path": relative}))
                if breaks == "malformed_arguments":
                    steps.append(("apply_patch", {"file": relative, "text": file.read_text()}))
                else:
                    steps.append(("apply_patch", {"path": relative, "content": file.read_text()}))
            if commands and breaks is None:
                steps.append(("run_command", {"command": commands[-1]}))
            steps.append(("finish", {"summary": f"Completed {task.id}."}))
        else:
            for grader in task.graders:
                if grader.type == "tool_contract":
                    for tool in grader.required_tools:
                        if tool == "finish":
                            continue
                        if breaks == "wrong_tool" and tool == "search_text":
                            steps.append(("read_file", {"path": "README.md"}))
                        else:
                            steps.append((tool, _default_args(tool, task)))
            if not steps:
                steps.append(("search_text", {"query": task.id.split("-")[-1]}))
            summary_file = self.solutions / f"{task.id}.finish.txt"
            summary = summary_file.read_text().strip() if summary_file.exists() else "done"
            if breaks == "wrong_tool":
                summary = "Could not locate the value."
            steps.append(("finish", {"summary": summary}))
        return steps

    async def _send_once(self, request: TraceRequest, model: str) -> WireResult:
        task = self._task_for(request)
        profile = model.split("/", 1)[1] if "/" in model else model
        plan = self._plan(task, profile)
        step = sum(1 for message in request.messages if message.role == "assistant")
        name, arguments = plan[min(step, len(plan) - 1)]
        call = ToolCall(id=f"fx-{task.id}-{step}", name=name, arguments=json.loads(json.dumps(arguments)))
        return WireResult(
            response=TraceResponse(content="", tool_calls=[call], finish_reason="tool_calls"),
            usage=TokenUsage(),
            raw={"fixture": True, "task": task.id, "step": step},
        )


def _default_args(tool: str, task: TaskSpec) -> dict[str, object]:
    if tool == "search_text":
        return {"query": "DEFAULT_TIMEOUT_SECONDS"}
    if tool == "read_file":
        return {"path": "config/shop.json"}
    if tool == "list_files":
        return {"path": "tests", "recursive": True}
    if tool == "run_command":
        commands = [g.command for g in task.graders if g.type in ("command", "test_count")]
        return {"command": commands[0] if commands else "python -m pytest -q tests/test_orders.py"}
    return {}
