"""Source registry: structured (SQLite) + unstructured (in-memory docs), all synthetic.

Every source declares ``owner``, ``sensitivity`` and ``mode_allow`` so the
access policy can gate *before* any retrieval happens.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

Sensitivity = Literal["public", "internal", "confidential"]
SourceKind = Literal["structured", "unstructured"]


@dataclass(frozen=True)
class Source:
    """One data source registered with the agent."""

    name: str
    kind: SourceKind
    owner: str
    sensitivity: Sensitivity
    mode_allow: Literal["personal", "company", "both"]
    description: str
    keywords: List[str] = field(default_factory=list)


class SourceRegistry:
    """Holds sources, the SQLite DB, and the in-memory doc store."""

    def __init__(self) -> None:
        self.sources: Dict[str, Source] = {}
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.docs: Dict[str, List[Dict[str, str]]] = {}

    # -- registration -------------------------------------------------
    def register_source(self, source: Source) -> None:
        self.sources[source.name] = source

    def get(self, name: str) -> Optional[Source]:
        return self.sources.get(name)

    def all_sources(self) -> List[Source]:
        return list(self.sources.values())

    # -- structured backends ------------------------------------------
    def register_table(
        self,
        source: Source,
        schema_sql: str,
        rows: List[tuple],
    ) -> None:
        """Register a structured source and seed its SQLite table."""
        self.register_source(source)
        cur = self.conn.cursor()
        cur.execute(schema_sql)
        if rows:
            placeholders = ",".join(["?"] * len(rows[0]))
            cur.executemany(f"INSERT INTO {source.name} VALUES ({placeholders})", rows)
        self.conn.commit()

    # -- unstructured backends ----------------------------------------
    def register_docs(self, source: Source, docs: List[Dict[str, str]]) -> None:
        """Register an unstructured source; docs are {id, title, text} dicts."""
        self.register_source(source)
        self.docs[source.name] = docs


def build_registry() -> SourceRegistry:
    """Build the registry with a fixed synthetic dataset."""
    reg = SourceRegistry()

    # Structured: sales ------------------------------------------------
    reg.register_table(
        Source(
            name="sales",
            kind="structured",
            owner="sales-ops",
            sensitivity="internal",
            mode_allow="company",
            description="Order-level sales records (region, rep, amount, quarter).",
            keywords=["sales", "revenue", "orders", "rep", "quota", "quarter"],
        ),
        "CREATE TABLE sales (order_id TEXT, region TEXT, rep TEXT, amount REAL, quarter TEXT)",
        [
            ("O-1001", "west", "a.chen", 4200.0, "Q3"),
            ("O-1002", "east", "b.okafor", 7350.0, "Q3"),
            ("O-1003", "west", "a.chen", 1980.0, "Q3"),
            ("O-1004", "central", "d.silva", 11200.0, "Q3"),
            ("O-1005", "east", "b.okafor", 2640.0, "Q2"),
        ],
    )

    # Structured: inventory --------------------------------------------
    reg.register_table(
        Source(
            name="inventory",
            kind="structured",
            owner="warehouse-ops",
            sensitivity="public",
            mode_allow="both",
            description="SKU stock levels and warehouse locations.",
            keywords=["inventory", "stock", "sku", "warehouse", "units"],
        ),
        "CREATE TABLE inventory (sku TEXT, product TEXT, units INTEGER, warehouse TEXT)",
        [
            ("SKU-1", "widget-a", 340, "reno"),
            ("SKU-2", "widget-b", 12, "reno"),
            ("SKU-3", "widget-c", 0, "austin"),
            ("SKU-4", "gadget-x", 215, "austin"),
        ],
    )

    # Structured: compensation (confidential) ---------------------------
    reg.register_table(
        Source(
            name="compensation",
            kind="structured",
            owner="hr",
            sensitivity="confidential",
            mode_allow="company",
            description="Employee compensation bands (restricted).",
            keywords=["salary", "compensation", "pay", "bonus", "band"],
        ),
        "CREATE TABLE compensation (employee TEXT, band TEXT, base REAL, bonus REAL)",
        [
            ("a.chen", "L4", 125000.0, 15000.0),
            ("b.okafor", "L5", 148000.0, 22000.0),
        ],
    )

    # Unstructured: policy docs -----------------------------------------
    reg.register_docs(
        Source(
            name="policy_docs",
            kind="unstructured",
            owner="legal",
            sensitivity="internal",
            mode_allow="company",
            description="Company policy documents (travel, expenses, remote work).",
            keywords=["policy", "travel", "expense", "reimbursement", "remote"],
        ),
        [
            {
                "id": "POL-1",
                "title": "Travel expense policy",
                "text": "Employees may claim up to $180 per night for lodging. "
                "Meals are reimbursed up to $75 per day with receipts. "
                "First-class flights require VP approval.",
            },
            {
                "id": "POL-2",
                "title": "Remote work policy",
                "text": "Employees may work remotely up to three days per week. "
                "Hardware requests go through IT with manager approval.",
            },
        ],
    )

    # Unstructured: meeting notes ---------------------------------------
    reg.register_docs(
        Source(
            name="meeting_notes",
            kind="unstructured",
            owner="a.chen",
            sensitivity="public",
            mode_allow="both",
            description="Personal and team meeting notes.",
            keywords=["meeting", "notes", "standup", "retro", "action"],
        ),
        [
            {
                "id": "MTG-1",
                "title": "Q3 planning notes",
                "text": "Action: a.chen to follow up on west region renewals. "
                "Decided: push widget-b restock before the holiday rush.",
            },
            {
                "id": "MTG-2",
                "title": "Personal reminders",
                "text": "Book dentist appointment. Renew parking pass by Friday.",
            },
        ],
    )

    # Unstructured: board minutes (confidential) --------------------------
    reg.register_docs(
        Source(
            name="board_minutes",
            kind="unstructured",
            owner="exec-office",
            sensitivity="confidential",
            mode_allow="company",
            description="Board meeting minutes (restricted).",
            keywords=["board", "acquisition", "merger", "strategy"],
        ),
        [
            {
                "id": "BRD-1",
                "title": "Q3 board minutes (excerpt)",
                "text": "The board reviewed the acquisition pipeline. "
                "No public disclosure until regulatory review completes.",
            },
        ],
    )

    return reg
