"""Deterministic PDF rendering for persisted experiment evidence."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

GREEN = colors.HexColor("#315D3F")
LIGHT_GREEN = colors.HexColor("#EEF5EC")
INK = colors.HexColor("#203027")
MUTED = colors.HexColor("#68776D")
LINE = colors.HexColor("#D7E1D5")
RED = colors.HexColor("#B94B40")
AMBER = colors.HexColor("#A56918")


def _text(value: Any) -> str:
    """Escape report values before they enter ReportLab's paragraph markup."""

    return (
        str(value if value is not None else "Unknown").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="RFTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=29,
            textColor=INK,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RFEyebrow",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=GREEN,
            tracking=1.2,
            uppercase=True,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RFH2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=INK,
            spaceBefore=14,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RFBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=13, textColor=INK
        )
    )
    styles.add(
        ParagraphStyle(
            name="RFSmall", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED
        )
    )
    styles.add(ParagraphStyle(name="RFCenter", parent=styles["RFBody"], alignment=TA_CENTER))
    styles.add(
        ParagraphStyle(
            name="RFTableHeader",
            parent=styles["RFSmall"],
            fontName="Helvetica-Bold",
            textColor=colors.white,
        )
    )
    return styles


def _header_footer(canvas, document) -> None:
    canvas.saveState()
    canvas.resetTransforms()
    width, _ = A4
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 14 * mm, width - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(width / 2, 9.5 * mm, f"ReplayForge evidence report  |  Page {document.page}")
    canvas.restoreState()


def _table(data: list[list[Any]], widths: list[float], header: bool = True) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands: list[tuple] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        commands.extend([("BACKGROUND", (0, 0), (-1, 0), GREEN), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)])
    for row in range(1 if header else 0, len(data)):
        if row % 2 == 0:
            commands.append(("BACKGROUND", (0, row), (-1, row), LIGHT_GREEN))
    table.setStyle(TableStyle(commands))
    return table


def render_pdf(snapshot: dict, experiment_id: str) -> bytes:
    """Render the authoritative snapshot into a stable, downloadable PDF."""

    decision = snapshot["decision"]
    if not decision:
        raise ValueError("experiment has no decision")
    styles = _styles()
    body, small, table_header = styles["RFBody"], styles["RFSmall"], styles["RFTableHeader"]
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=17 * mm,
        title=f"ReplayForge experiment {experiment_id}",
        author="ReplayForge",
    )
    outcome = str(decision["outcome"]).upper()
    outcome_color = GREEN if outcome == "PASS" else AMBER if outcome == "WARN" else RED
    story: list[Any] = [
        Paragraph("AUTONOMOUS MODEL-MIGRATION EVIDENCE", styles["RFEyebrow"]),
        Paragraph(f"Experiment {_text(experiment_id)}", styles["RFTitle"]),
        Paragraph(_text(decision["summary"]), body),
        Spacer(1, 7 * mm),
    ]
    summary = Table(
        [
            [Paragraph("RELEASE DECISION", small), Paragraph("WORKLOAD", small), Paragraph("MODE", small)],
            [
                Paragraph(f"<b><font color='{outcome_color.hexval()}'>{outcome}</font></b>", styles["RFCenter"]),
                Paragraph(f"<b>{len(snapshot['tasks'])} paired tasks</b>", styles["RFCenter"]),
                Paragraph(f"<b>{'SIMULATION' if snapshot['fixture_mode'] else 'LIVE MODELS'}</b>", styles["RFCenter"]),
            ],
        ],
        colWidths=[58 * mm, 58 * mm, 58 * mm],
    )
    summary.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.7, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.45, LINE),
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GREEN),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([summary, Paragraph("Experiment identity", styles["RFH2"])])
    identity = [
        [Paragraph("Field", table_header), Paragraph("Persisted value", table_header)],
        [Paragraph("Suite", body), Paragraph(_text(snapshot["suite"]["name"]), body)],
        [Paragraph("Suite digest", body), Paragraph(_text(snapshot["suite"]["digest"]), small)],
        [Paragraph("Source revision", body), Paragraph(_text(snapshot.get("git_sha")), small)],
        [
            Paragraph("Baseline lane", body),
            Paragraph(f"{_text(snapshot['baseline']['provider'])}:{_text(snapshot['baseline']['model'])}", small),
        ],
        [
            Paragraph("Candidate lane", body),
            Paragraph(f"{_text(snapshot['candidate']['provider'])}:{_text(snapshot['candidate']['model'])}", small),
        ],
    ]
    story.extend([_table(identity, [42 * mm, 132 * mm]), Paragraph("Paired task outcomes", styles["RFH2"])])

    def pair_table(pairs: list[dict]) -> Table:
        pair_rows = [
            [
                Paragraph("Task", table_header),
                Paragraph("Critical", table_header),
                Paragraph("Outcome", table_header),
                Paragraph("Investigation", table_header),
            ]
        ]
        for pair in pairs:
            finding = pair.get("investigation") or {}
            finding_text = finding.get("summary") or "No regression finding"
            pair_rows.append(
                [
                    Paragraph(_text(pair["task_id"]), body),
                    Paragraph("Yes" if pair["critical"] else "No", body),
                    Paragraph(_text(pair["outcome"]).replace("_", " ").title(), body),
                    Paragraph(_text(finding_text), small),
                ]
            )
        return _table(pair_rows, [38 * mm, 20 * mm, 38 * mm, 78 * mm])

    pairs = snapshot["pairs"]
    story.append(pair_table(pairs[:8]))
    if len(pairs) > 8:
        story.extend(
            [
                PageBreak(),
                Paragraph("PAIRED EVIDENCE", styles["RFEyebrow"]),
                Paragraph("Paired task outcomes (continued)", styles["RFH2"]),
                pair_table(pairs[8:]),
            ]
        )
    violations = decision.get("violations") or []
    story.extend(
        [
            Paragraph("Release policy", styles["RFH2"]),
            Paragraph(
                f"Policy version: <b>{_text(decision.get('policy_version'))}</b>. The model agents cannot change these rules or this outcome.",
                body,
            ),
        ]
    )
    if violations:
        violation_rows = [
            [Paragraph("Rule", table_header), Paragraph("Severity", table_header), Paragraph("Evidence", table_header)]
        ]
        for violation in violations:
            violation_rows.append(
                [
                    Paragraph(_text(violation.get("rule")), body),
                    Paragraph(_text(violation.get("severity")).upper(), body),
                    Paragraph(_text(violation.get("message")), small),
                ]
            )
        story.extend([Spacer(1, 3 * mm), _table(violation_rows, [45 * mm, 25 * mm, 104 * mm])])
    else:
        story.append(Paragraph("No policy violations were recorded.", body))
    story.extend(
        [
            PageBreak(),
            Paragraph("Measured evidence", styles["RFEyebrow"]),
            Paragraph("Metrics and provenance", styles["RFTitle"]),
        ]
    )
    metric_rows = [
        [
            Paragraph("Lane", table_header),
            Paragraph("Metric", table_header),
            Paragraph("Value", table_header),
            Paragraph("Kind", table_header),
            Paragraph("Samples", table_header),
        ]
    ]
    for metric in snapshot["metrics"]:
        value = "Unknown" if metric.get("value") is None else f"{metric['value']} {metric.get('unit', '')}".strip()
        metric_rows.append(
            [
                Paragraph(_text(metric.get("lane")), small),
                Paragraph(_text(metric.get("name")), small),
                Paragraph(_text(value), small),
                Paragraph(_text(metric.get("measurement_kind")), small),
                Paragraph(_text(metric.get("sample_count")), small),
            ]
        )
    story.append(_table(metric_rows, [27 * mm, 53 * mm, 34 * mm, 41 * mm, 19 * mm]))
    story.extend(
        [
            Paragraph("Interpretation boundaries", styles["RFH2"]),
            Paragraph(
                "This report is generated from persisted runs, grader results, investigations, metrics and the stored release decision. Fixture mode is a scripted rehearsal and is never presented as live model evidence. Unknown cost or usage remains unknown rather than becoming zero.",
                body,
            ),
            Spacer(1, 5 * mm),
            Paragraph(
                f"Generated for experiment {_text(experiment_id)}. The Markdown report and complete tool traces remain available in ReplayForge.",
                small,
            ),
        ]
    )
    document.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return stream.getvalue()
