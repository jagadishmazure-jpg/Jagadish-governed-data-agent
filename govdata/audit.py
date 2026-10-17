"""Hash-chained access ledger: every request, allowed and denied, is logged."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List

from govdata.retrieve import RetrievalResult
from govdata.router import RetrievalPlan


@dataclass
class LedgerEntry:
    seq: int
    ts: str
    role: str
    mode: str
    question: str
    allowed_sources: List[str]
    denied_sources: List[Dict[str, str]]
    queries_run: List[str]
    row_count: int
    prev_hash: str
    entry_hash: str = ""


def _hash(payload: Dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


class AccessLedger:
    def __init__(self) -> None:
        self.entries: List[LedgerEntry] = []

    def log(self, plan: RetrievalPlan, result: RetrievalResult) -> LedgerEntry:
        prev = self.entries[-1].entry_hash if self.entries else "GENESIS"
        body = {
            "seq": len(self.entries),
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": plan.role,
            "mode": plan.mode,
            "question": plan.question,
            "allowed_sources": plan.allowed_names,
            "denied_sources": [
                {"name": d.name, "rule": d.rule} for d in plan.denied
            ],
            "queries_run": result.queries_run,
            "row_count": len(result.rows),
            "prev_hash": prev,
        }
        entry = LedgerEntry(**body, entry_hash=_hash(body))
        self.entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        prev = "GENESIS"
        for i, e in enumerate(self.entries):
            if e.seq != i or e.prev_hash != prev:
                return False
            body = {k: v for k, v in asdict(e).items() if k != "entry_hash"}
            if _hash(body) != e.entry_hash:
                return False
            prev = e.entry_hash
        return True
