"""Phase 1 exit check: prove a live NVIDIA model call on Nebius Token Factory, then run five paired cases.

Usage (key stays in the environment, never on the command line):
    export NEBIUS_TOKEN_FACTORY_API_KEY=...
    .venv/bin/python scripts/live_smoke.py [--model <exact id from the catalog>] [--baseline fixture:fixture/reference]

Writes redacted evidence under evidence/ (gitignored).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/engine/src"))

from replayforge.cassettes import load_suite  # noqa: E402
from replayforge.orchestration.paired import run_experiment  # noqa: E402
from replayforge.providers import LaneConfig, NebiusTokenFactoryProvider  # noqa: E402
from replayforge.redaction import redact  # noqa: E402

FIVE = ["repair-slug", "repair-discount", "tool-find-timeout", "nav-money-formatter", "testgen-shipping"]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="exact NVIDIA model id from the live catalog (default: first NVIDIA entry)")
    parser.add_argument("--baseline", default="fixture:fixture/reference")
    args = parser.parse_args()
    evidence = ROOT / "evidence" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    evidence.mkdir(parents=True, exist_ok=True)

    provider = NebiusTokenFactoryProvider()
    if not provider.configured:
        print("NEBIUS_TOKEN_FACTORY_API_KEY is not set.", file=sys.stderr)
        return 2
    try:
        catalog = await provider.list_models()
        (evidence / "catalog.json").write_text(
            redact(
                json.dumps(
                    {
                        "fetched_at": catalog.fetched_at.isoformat(),
                        "base_url": catalog.base_url,
                        "models": [{"id": m.id, "owned_by": m.owned_by, "nvidia": m.is_nvidia} for m in catalog.models],
                    },
                    indent=2,
                )
            )
        )
        nvidia = [m.id for m in catalog.nvidia]
        print(f"catalog: {len(catalog.models)} models, {len(nvidia)} NVIDIA: {nvidia}")
        model = args.model or (nvidia[0] if nvidia else None)
        if not model or model not in {m.id for m in catalog.models}:
            print("No accessible NVIDIA model found in this account's catalog.", file=sys.stderr)
            return 3
        validation = await provider.validate_model(model)
        (evidence / "validation.json").write_text(redact(json.dumps(validation, indent=2)))
        print(f"validated {model}: {validation}")
    finally:
        await provider.aclose()

    suite = load_suite(ROOT / "fixtures/suites/demo-suite.yaml")
    base_provider, _, base_model = args.baseline.partition(":")
    result = await run_experiment(
        suite, LaneConfig(base_provider, base_model), LaneConfig("nebius", model), task_ids=FIVE, concurrency=2
    )
    rows = [
        {
            "task": p.task.id,
            "baseline": p.baseline.passed,
            "candidate": p.candidate.passed,
            "outcome": p.outcome,
            "finding": p.finding.as_dict() if p.finding else None,
            "candidate_failure": p.candidate.run.failure_kind,
            "provider_response_ids": p.candidate.run.trace.metadata.get("provider_response_ids"),
        }
        for p in result.pairs
    ]
    with (evidence / "traces.jsonl").open("w") as handle:
        for p in result.pairs:
            for lane in (p.baseline, p.candidate):
                handle.write(redact(lane.run.trace.model_dump_json()) + "\n")
    (evidence / "summary.json").write_text(
        redact(
            json.dumps(
                {
                    "suite_digest": result.suite_digest,
                    "lanes": result.lane_labels,
                    "pairs": rows,
                    "metrics": result.metrics,
                    "decision": result.decision.as_dict(),
                },
                indent=2,
                default=str,
            )
        )
    )
    for row in rows:
        print(row["task"], "baseline", row["baseline"], "candidate", row["candidate"], row["candidate_failure"] or "")
    print(f"decision {result.decision.outcome.upper()}; evidence in {evidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
