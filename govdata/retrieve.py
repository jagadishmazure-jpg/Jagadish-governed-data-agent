"""Retrieval: executes only what the plan allowed.

Structured sources run intent-derived, parameterised SQL against SQLite.
Unstructured sources run keyword search over the in-memory doc store.
Every returned row carries its source citation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from govdata.router import RetrievalPlan
from govdata.sources import SourceRegistry

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_WORD.findall(text.lower()))


@dataclass
class RetrievalResult:
    rows: List[Dict] = field(default_factory=list)
    queries_run: List[str] = field(default_factory=list)

    @property
    def sources_used(self) -> List[str]:
        seen: List[str] = []
        for row in self.rows:
            s = row.get("source")
            if s and s not in seen:
                seen.append(s)
        return seen


def _sql_for(source_name: str, question: str) -> Tuple[str, tuple, str]:
    """Derive a safe, read-only query from the question (deterministic)."""
    q = question.lower()
    if source_name == "sales":
        if "region" in q:
            return (
                "SELECT region, SUM(amount) AS total FROM sales GROUP BY region",
                (),
                "sales by region",
            )
        if any(w in q for w in ("total", "sum", "revenue", "how much")):
            return (
                "SELECT SUM(amount) AS total FROM sales",
                (),
                "total sales",
            )
        for rep in ("a.chen", "b.okafor", "d.silva"):
            if rep.replace(".", " ") in q or rep in q:
                return (
                    "SELECT * FROM sales WHERE rep = ?",
                    (rep,),
                    f"sales by {rep}",
                )
        return ("SELECT * FROM sales LIMIT 5", (), "recent sales rows")
    if source_name == "inventory":
        if any(w in q for w in ("low", "restock", "out of stock", "running out")):
            return (
                "SELECT * FROM inventory WHERE units < 20",
                (),
                "low-stock items",
            )
        m = re.search(r"sku-\d+", q)
        if m:
            return (
                "SELECT * FROM inventory WHERE sku = ?",
                (m.group(0).upper(),),
                f"lookup {m.group(0).upper()}",
            )
        return ("SELECT * FROM inventory", (), "full inventory")
    if source_name == "compensation":
        return (
            "SELECT employee, band, base FROM compensation",
            (),
            "compensation bands",
        )
    return (f"SELECT * FROM {source_name} LIMIT 5", (), f"sample of {source_name}")


def _search_docs(
    registry: SourceRegistry, source_name: str, question: str, top_k: int = 2
) -> List[Dict]:
    q_tokens = _tokens(question) - {"what", "is", "the", "a", "an", "of", "for", "do"}
    scored = []
    for doc in registry.docs.get(source_name, []):
        d_tokens = _tokens(doc["title"] + " " + doc["text"])
        overlap = q_tokens & d_tokens
        if overlap:
            scored.append((len(overlap), doc))
    scored.sort(key=lambda t: t[0], reverse=True)
    rows = []
    for _, doc in scored[:top_k]:
        rows.append(
            {
                "doc_id": doc["id"],
                "title": doc["title"],
                "snippet": doc["text"][:160],
                "source": source_name,
                "citation": f"{source_name}:{doc['id']}",
            }
        )
    return rows


def execute_plan(
    plan: RetrievalPlan, registry: SourceRegistry, max_rows: int = 25
) -> RetrievalResult:
    """Run the plan. Only ``plan.planned`` sources are ever touched."""
    result = RetrievalResult()
    for planned in plan.planned:
        name = planned.source.name
        if planned.strategy == "sql":
            sql, params, desc = _sql_for(name, plan.question)
            cur = registry.conn.execute(sql, params)
            cols = [d[0] for d in cur.description]
            for tup in cur.fetchall()[:max_rows]:
                row = dict(zip(cols, tup))
                row["source"] = name
                key = (
                    row.get("order_id")
                    or row.get("sku")
                    or row.get("employee")
                    or row.get("region")
                    or row.get("quarter")
                    or "agg"
                )
                row["citation"] = f"{name}:{key}"
                result.rows.append(row)
            result.queries_run.append(f"SQL [{name}]: {sql}  -- {desc}")
        else:
            rows = _search_docs(registry, name, plan.question)
            result.rows.extend(rows[:max_rows])
            result.queries_run.append(f"KEYWORD [{name}]: {plan.question[:60]}")
    return result
