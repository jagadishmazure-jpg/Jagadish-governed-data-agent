"""Request router: governance first, retrieval planning second.

The router scores every registered source against the question by keyword
overlap, then runs the access policy over the candidates. Denied sources
are dropped *before* any retrieval runs — the retriever never sees them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

from govdata.policy import AccessPolicy, Decision, Mode, Role
from govdata.sources import Source, SourceRegistry

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_WORD.findall(text.lower()))


@dataclass
class PlannedSource:
    source: Source
    strategy: str  # "sql" for structured, "keyword" for unstructured
    score: float


@dataclass
class Denial:
    name: str
    rule: str
    reason: str


@dataclass
class RetrievalPlan:
    question: str
    role: Role
    mode: Mode
    planned: List[PlannedSource] = field(default_factory=list)
    denied: List[Denial] = field(default_factory=list)

    @property
    def allowed_names(self) -> List[str]:
        return [p.source.name for p in self.planned]


def route_request(
    question: str,
    role: Role,
    mode: Mode,
    registry: SourceRegistry,
    policy: AccessPolicy | None = None,
    min_score: float = 0.1,
) -> RetrievalPlan:
    """Build a retrieval plan for the question.

    1. Score sources by keyword overlap with the question.
    2. Apply the access policy to each candidate (and to every source
       below threshold, so denials are explicit in the audit trail).
    3. Return the plan; retrieval executes only ``planned`` sources.
    """
    policy = policy or AccessPolicy()
    q_tokens = _tokens(question)
    plan = RetrievalPlan(question=question, role=role, mode=mode)

    for source in registry.all_sources():
        keywords = set(k.lower() for k in source.keywords)
        overlap = q_tokens & keywords
        score = len(overlap) / max(len(q_tokens), 1)

        decision: Decision = policy.can_access(role, mode, source)
        if not decision.allowed:
            plan.denied.append(
                Denial(name=source.name, rule=decision.rule, reason=decision.reason)
            )
            continue

        if score >= min_score:
            strategy = "sql" if source.kind == "structured" else "keyword"
            plan.planned.append(
                PlannedSource(source=source, strategy=strategy, score=round(score, 3))
            )

    plan.planned.sort(key=lambda p: p.score, reverse=True)
    return plan
