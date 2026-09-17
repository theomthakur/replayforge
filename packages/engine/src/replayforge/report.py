"""Markdown and JSON experiment reports with redaction."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from replayforge.redaction import redact


def _fmt(value: object, unit: str) -> str:
    if value is None:
        return "unknown"
    if unit == "ratio":
        return f"{float(value):.0%}"  # type: ignore[arg-type]
    if unit == "usd":
        return f"${float(value):.4f}"  # type: ignore[arg-type]
    if unit == "ms":
        return f"{float(value) / 1000:.1f} s"  # type: ignore[arg-type]
    return f"{float(value):,.0f}"  # type: ignore[arg-type]


def render_markdown(
    *,
    title: str,
    suite_digest: str,
    lanes: Mapping[str, str],
    pairs: Sequence[Mapping[str, object]],
    metrics: Sequence[Mapping[str, object]],
    comparison: Mapping[str, object] | None,
    decision: Mapping[str, object],
    fixture_mode: bool,
) -> str:
    lines = [f"# {title}", ""]
    if fixture_mode:
        lines += [
            "> **Fixture mode.** At least one lane used the scripted fixture provider. These are not model results.",
            "",
        ]
    lines += [f"- Suite digest: `{suite_digest}`"] + [f"- {name}: `{label}`" for name, label in lanes.items()] + [""]
    lines += [
        f"## Decision: **{str(decision['outcome']).upper()}** (policy {decision.get('policy_version')})",
        "",
    ]
    for violation in decision.get("violations", []):  # type: ignore[union-attr]
        lines.append(f"- {violation['severity']}: {violation['message']}")  # type: ignore[index]
    lines += [
        "",
        "## Metrics",
        "",
        "| Metric | Baseline | Candidate | Kind | n |",
        "|---|---|---|---|---|",
    ]
    names = sorted({str(m["name"]) for m in metrics})
    for name in names:
        row = {str(m["lane"]): m for m in metrics if m["name"] == name}
        b, c = row.get("baseline"), row.get("candidate")
        unit = str((b or c or {}).get("unit", ""))
        kind = str((c or b or {}).get("measurement_kind", ""))
        n = (c or b or {}).get("sample_count", "")
        lines.append(
            f"| {name} | {_fmt(b['value'] if b else None, unit)} | {_fmt(c['value'] if c else None, unit)} | {kind} | {n} |"
        )
    if comparison:
        lines += [
            "",
            "## Paired comparison",
            "",
            f"- n = {comparison['n']}, McNemar p = {float(comparison['mcnemar_p_value']):.3g}",  # type: ignore[arg-type]
            f"- {comparison['conclusion']}",
        ]
    lines += [
        "",
        "## Cases",
        "",
        "| Task | Critical | Baseline | Candidate | Finding (hypothesis) |",
        "|---|---|---|---|---|",
    ]
    for pair in pairs:
        finding = pair.get("finding") or {}
        lines.append(
            f"| {pair['task_id']} | {'yes' if pair['critical'] else ''} | {'pass' if pair['baseline_passed'] else 'fail'} | "
            f"{'pass' if pair['candidate_passed'] else 'fail'} | {finding.get('category', '')} {finding.get('summary', '')} |"  # type: ignore[union-attr]
        )
    return redact("\n".join(lines) + "\n")


def to_json(data: object) -> str:
    return redact(json.dumps(data, indent=2, default=str))
