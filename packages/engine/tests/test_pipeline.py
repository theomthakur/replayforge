from replayforge.orchestration.paired import run_experiment
from replayforge.policy import MigrationPolicy
from replayforge.providers import LaneConfig


async def test_fixture_reference_passes_every_task(suite):
    result = await run_experiment(
        suite,
        LaneConfig("fixture", "fixture/reference"),
        LaneConfig("fixture", "fixture/reference"),
        concurrency=4,
    )
    assert len(result.pairs) == 20
    assert all(p.baseline.passed and p.candidate.passed for p in result.pairs)
    assert result.decision.outcome == "pass"


async def test_variant_regressions_are_detected_and_explained(suite):
    result = await run_experiment(
        suite,
        LaneConfig("fixture", "fixture/reference"),
        LaneConfig("fixture", "fixture/variant"),
        task_ids=["repair-discount", "tool-find-timeout", "repair-slug"],
        policy=MigrationPolicy(),
    )
    by_task = {p.task.id: p for p in result.pairs}
    assert by_task["repair-slug"].outcome == "both_pass"
    assert by_task["repair-discount"].outcome == "candidate_regressed"
    assert by_task["repair-discount"].finding.category == "malformed_arguments"
    assert any(ref.startswith("step:") for ref in by_task["repair-discount"].finding.evidence_refs)
    assert by_task["tool-find-timeout"].finding.category == "tool_selection"
    assert result.decision.outcome == "block"
    rules = {v.rule for v in result.decision.violations}
    assert {"max_pass_rate_drop", "critical_tasks_must_pass"} <= rules


async def test_editing_protected_tests_fails_grading(suite):
    from benchtrace.trace import TraceRecord, TraceRequest
    from replayforge.grading.coding import grade_case
    from replayforge.orchestration.agent import AgentRun
    from replayforge.sandbox import LocalSandbox

    box = LocalSandbox(suite.fixture_path)
    try:
        before = box.snapshot()
        (box.workspace / "tests/test_slug.py").write_text("def test_ok():\n    assert True\n")
        trace = TraceRecord(
            run_id="r",
            task_id="repair-slug",
            case_id="default",
            provider="x",
            model="y",
            request=TraceRequest(messages=[]),
            status="completed",
        )
        grades = await grade_case(suite.cassette.task("repair-slug"), AgentRun(trace=trace), box, before, 30)
        by_name = {g.grader: g for g in grades}
        assert by_name["command"].score == 1.0  # the gamed test passes...
        assert by_name["forbidden_paths"].score == 0.0  # ...but the protected-path grader catches it
    finally:
        box.close()
