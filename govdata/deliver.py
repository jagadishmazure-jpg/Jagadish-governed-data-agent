"""Delivery: one retrieval result, three output formats.

- ``chat``   — natural-language summary with citations.
- ``table``  — rows for dashboards (list of dicts).
- ``report`` — structured report shape: title, sections, tables, sources
  (the report *shape*; no PDF bytes are generated here).
"""

from __future__ import annotations

from typing import Dict, List, Literal

from govdata.retrieve import RetrievalResult
from govdata.router import RetrievalPlan

Format = Literal["chat", "table", "report"]


def deliver(
    plan: RetrievalPlan, result: RetrievalResult, fmt: Format = "chat"
) -> Dict | List[Dict] | str:
    if fmt == "chat":
        return _as_chat(plan, result)
    if fmt == "table":
        return _as_table(result)
    if fmt == "report":
        return _as_report(plan, result)
    raise ValueError(f"unknown format: {fmt}")


def _as_chat(plan: RetrievalPlan, result: RetrievalResult) -> str:
    lines = [f"Here's what I found for: \"{plan.question}\""]
    if not result.rows:
        lines.append("No results from the sources I can access.")
    else:
        lines.append(f"{len(result.rows)} result(s) from: {', '.join(result.sources_used)}.")
        for row in result.rows[:5]:
            facts = ", ".join(
                f"{k}={v}" for k, v in row.items() if k not in ("source", "citation")
            )
            lines.append(f"- {facts} [{row['citation']}]")
        if len(result.rows) > 5:
            lines.append(f"...and {len(result.rows) - 5} more.")
    if plan.denied:
        lines.append(
            "I couldn't use: "
            + ", ".join(f"{d.name} ({d.rule})" for d in plan.denied)
            + "."
        )
    return "\n".join(lines)


def _as_table(result: RetrievalResult) -> List[Dict]:
    return [dict(r) for r in result.rows]


def _as_report(plan: RetrievalPlan, result: RetrievalResult) -> Dict:
    tables: Dict[str, List[Dict]] = {}
    for row in result.rows:
        tables.setdefault(row.get("source", "unknown"), []).append(
            {k: v for k, v in row.items() if k != "citation"}
        )
    return {
        "title": f"Data report: {plan.question}",
        "sections": [
            {
                "heading": "Summary",
                "body": f"{len(result.rows)} result(s) across {len(result.sources_used)} source(s).",
            },
            {
                "heading": "Access",
                "body": {
                    "role": plan.role,
                    "mode": plan.mode,
                    "sources_used": result.sources_used,
                    "sources_denied": [d.name for d in plan.denied],
                },
            },
        ],
        "tables": tables,
        "sources": sorted(
            {r["citation"] for r in result.rows if r.get("citation")}
        ),
        "queries_run": list(result.queries_run),
    }
