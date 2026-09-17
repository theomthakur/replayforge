from benchtrace.trace import (
    GraderOutput,
    ModelCall,
    TokenUsage,
    TraceRecord,
    TraceRequest,
    TraceResponse,
)
from replayforge.costing import lane_metrics
from replayforge.policy import GITHUB_CONCLUSION, MigrationPolicy, PairFact, evaluate_policy


def _pairs(base, cand, critical=False):
    return [PairFact(f"t{i}", critical, b, c) for i, (b, c) in enumerate(zip(base, cand, strict=False))]


def test_pass_when_equal():
    decision = evaluate_policy(MigrationPolicy(), _pairs([True] * 10, [True] * 10), [])
    assert decision.outcome == "pass" and not decision.violations


def test_drop_exactly_at_limit_passes():
    policy = MigrationPolicy(max_pass_rate_drop=0.1)
    decision = evaluate_policy(policy, _pairs([True] * 10, [True] * 9 + [False]), [])
    assert decision.outcome == "pass"


def test_drop_above_limit_blocks():
    decision = evaluate_policy(MigrationPolicy(), _pairs([True] * 10, [True] * 9 + [False]), [])
    assert decision.outcome == "block"


def test_critical_failure_blocks_even_without_rate_drop():
    policy = MigrationPolicy(max_pass_rate_drop=1.0)
    pairs = [PairFact("crit", True, False, False)]
    assert evaluate_policy(policy, pairs, []).outcome == "block"


def test_latency_warns():
    metrics = [{"lane": "candidate", "name": "latency_p95_ms", "value": 20000.0}]
    decision = evaluate_policy(MigrationPolicy(), _pairs([True], [True]), metrics)
    assert decision.outcome == "warn"


def test_unknown_cost_warns_when_saving_required():
    decision = evaluate_policy(MigrationPolicy(require_lower_cost_per_success=True), _pairs([True], [True]), [])
    assert decision.outcome == "warn"


def test_no_pairs_blocks():
    assert evaluate_policy(MigrationPolicy(), [], []).outcome == "block"


def test_github_mapping():
    assert GITHUB_CONCLUSION == {"pass": "success", "warn": "neutral", "block": "failure"}


def _trace(passed: bool, cost: float, priced: bool, tokens: int, latency: float) -> TraceRecord:
    request = TraceRequest(messages=[])
    call = ModelCall(
        provider="nebius",
        model="m",
        purpose="agent",
        request=request,
        response=TraceResponse(),
        usage=TokenUsage(input_tokens=tokens, output_tokens=tokens),
        cost_usd=cost,
        pricing_known=priced,
    )
    return TraceRecord(
        run_id="r",
        task_id="t",
        case_id="c",
        provider="nebius",
        model="m",
        request=request,
        status="completed",
        model_calls=[call],
        latency_ms=latency,
        usage=call.usage,
        grader_outputs=[GraderOutput(grader="g", score=1.0 if passed else 0.0, reason="r")],
    )


def test_cost_unknown_is_none_not_zero():
    metrics = {m.name: m for m in lane_metrics("candidate", [_trace(True, 0.0, False, 10, 100.0)] * 5)}
    assert metrics["cost_per_success_usd"].value is None
    assert metrics["cost_per_success_usd"].measurement_kind == "estimated"


def test_cost_per_success_derived():
    traces = [_trace(True, 0.01, True, 10, 100.0)] * 4 + [_trace(False, 0.01, True, 10, 100.0)]
    metrics = {m.name: m for m in lane_metrics("candidate", traces)}
    assert metrics["cost_per_success_usd"].measurement_kind == "derived"
    assert abs(metrics["cost_per_success_usd"].value - 0.05 / 4) < 1e-9


def test_latency_needs_enough_samples():
    metrics = {m.name: m for m in lane_metrics("candidate", [_trace(True, 0, False, 0, 100.0)] * 3)}
    assert metrics["latency_p95_ms"].value is None and metrics["latency_p95_ms"].sample_count == 3
