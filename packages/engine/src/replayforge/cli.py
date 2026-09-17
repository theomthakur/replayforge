"""ReplayForge command line: validate suites, inspect the Nebius catalog, run paired experiments."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from replayforge.cassettes import CassetteError, load_suite
from replayforge.orchestration.case import CaseResult
from replayforge.orchestration.paired import run_experiment
from replayforge.policy import MigrationPolicy
from replayforge.providers import LaneConfig, NebiusTokenFactoryProvider
from replayforge.report import render_markdown, to_json


def _lane(value: str) -> LaneConfig:
    provider, _, model = value.partition(":")
    if not model:
        raise argparse.ArgumentTypeError("use provider:model, e.g. fixture:fixture/reference or nebius:<model-id>")
    return LaneConfig(provider=provider, model=model)


async def _models() -> int:
    provider = NebiusTokenFactoryProvider()
    if not provider.configured:
        print("NEBIUS_TOKEN_FACTORY_API_KEY is not set.", file=sys.stderr)
        return 2
    try:
        catalog = await provider.list_models()
    finally:
        await provider.aclose()
    print(f"catalog fetched {catalog.fetched_at.isoformat()} from {catalog.base_url}")
    for model in catalog.models:
        print(f"{'NVIDIA ' if model.is_nvidia else '       '} {model.id}  ({model.owned_by or '-'})")
    return 0


async def _validate_model(model: str) -> int:
    provider = NebiusTokenFactoryProvider()
    try:
        evidence = await provider.validate_model(model)
    finally:
        await provider.aclose()
    print(json.dumps(evidence, indent=2))
    return 0


async def _run(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    async def progress(result: CaseResult) -> None:
        mark = "PASS" if result.passed else "FAIL"
        print(
            f"  {result.lane:9} {result.task_id:28} {mark} {result.run.failure_kind or ''}",
            flush=True,
        )
        with (out / f"traces-{result.lane}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(result.run.trace.model_dump_json() + "\n")

    tasks = args.tasks.split(",") if args.tasks else None
    print(f"suite {suite.cassette.suite.id} digest {suite.digest}")
    result = await run_experiment(
        suite,
        args.baseline,
        args.candidate,
        policy=MigrationPolicy(),
        task_ids=tasks,
        concurrency=args.concurrency,
        on_result=progress,
    )
    pairs = [
        {
            "task_id": p.task.id,
            "critical": p.task.critical,
            "baseline_passed": p.baseline.passed,
            "candidate_passed": p.candidate.passed,
            "outcome": p.outcome,
            "finding": p.finding.as_dict() if p.finding else None,
        }
        for p in result.pairs
    ]
    fixture_mode = "fixture" in (args.baseline.provider, args.candidate.provider)
    report = render_markdown(
        title="ReplayForge experiment",
        suite_digest=result.suite_digest,
        lanes=result.lane_labels,
        pairs=pairs,
        metrics=result.metrics,
        comparison=result.comparison,
        decision=result.decision.as_dict(),
        fixture_mode=fixture_mode,
    )
    (out / "report.md").write_text(report, encoding="utf-8")
    (out / "summary.json").write_text(
        to_json(
            {
                "run_id": result.run_id,
                "suite_digest": result.suite_digest,
                "lanes": result.lane_labels,
                "fixture_mode": fixture_mode,
                "pairs": pairs,
                "metrics": result.metrics,
                "comparison": result.comparison,
                "decision": result.decision.as_dict(),
            }
        ),
        encoding="utf-8",
    )
    print(f"decision: {result.decision.outcome.upper()}  report: {out / 'report.md'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="replayforge")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate a cassette suite")
    validate.add_argument("suite")
    sub.add_parser("models", help="list the live Nebius Token Factory catalog")
    check = sub.add_parser("validate-model", help="run one tiny completion against a Nebius model")
    check.add_argument("model")
    run = sub.add_parser("run", help="run a paired experiment")
    run.add_argument("--suite", required=True)
    run.add_argument("--baseline", type=_lane, required=True)
    run.add_argument("--candidate", type=_lane, required=True)
    run.add_argument("--tasks", help="comma-separated task ids (default: all)")
    run.add_argument("--concurrency", type=int, default=3)
    run.add_argument("--out", default="data/runs/latest")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            suite = load_suite(args.suite)
            print(f"ok: {len(suite.cassette.tasks)} tasks, digest {suite.digest}")
            return 0
        if args.command == "models":
            return asyncio.run(_models())
        if args.command == "validate-model":
            return asyncio.run(_validate_model(args.model))
        return asyncio.run(_run(args))
    except CassetteError as error:
        print(f"invalid suite: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
