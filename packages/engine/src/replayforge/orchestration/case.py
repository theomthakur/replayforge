"""Run one lane of one case end to end: fresh sandbox, agent loop, deterministic grading."""

from __future__ import annotations

from dataclasses import dataclass

from benchtrace.providers import Provider

from replayforge.cassettes.schema import LoadedSuite, TaskSpec
from replayforge.grading.coding import GRADER_VERSION, grade_case
from replayforge.orchestration.agent import AgentRun, EventSink, _no_events, run_agent_case
from replayforge.providers import LaneConfig
from replayforge.sandbox import create_sandbox
from replayforge.sandbox.base import SandboxError


@dataclass(slots=True)
class CaseResult:
    lane: str
    task_id: str
    case_id: str
    repeat: int
    run: AgentRun
    grader_version: str

    @property
    def passed(self) -> bool:
        return self.run.trace.passed


async def run_case(
    *,
    run_id: str,
    suite: LoadedSuite,
    task: TaskSpec,
    lane_name: str,
    lane: LaneConfig,
    provider: Provider,
    sandbox_backend: str = "local",
    case_id: str = "default",
    repeat: int = 0,
    on_event: EventSink = _no_events,
) -> CaseResult:
    limits = suite.cassette.limits_for(task)
    sandbox = create_sandbox(suite.fixture_path, sandbox_backend, max_output_chars=limits.max_tool_output_chars)
    try:
        setup_command = suite.cassette.suite.setup_command
        if setup_command:
            await on_event("case.setup", {"command": setup_command})
            setup = await sandbox.run(setup_command, suite.cassette.suite.default_timeout_seconds)
            if setup.timed_out or setup.exit_code != 0:
                reason = "timed out" if setup.timed_out else f"exited with {setup.exit_code}"
                raise SandboxError(f"suite setup command {reason}: {setup.stderr[-500:]}")
        baseline_snapshot = sandbox.snapshot()
        await on_event("case.started", {"sandbox": sandbox.info.backend})
        run = await run_agent_case(
            run_id=run_id,
            cassette=suite.cassette,
            task=task,
            lane=lane,
            provider=provider,
            sandbox=sandbox,
            case_id=case_id,
            repeat=repeat,
            on_event=on_event,
        )
        await on_event("case.grading", {})
        grades = await grade_case(task, run, sandbox, baseline_snapshot, suite.cassette.suite.default_timeout_seconds)
        run.trace = run.trace.model_copy(update={"grader_outputs": grades})
        return CaseResult(lane_name, task.id, case_id, repeat, run, GRADER_VERSION)
    finally:
        sandbox.close()
