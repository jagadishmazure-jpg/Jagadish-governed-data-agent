# Jagadish-governed-data-agent

One agent that answers questions across structured and unstructured data —
with data governance enforced like employee access, not bolted on after.

## The problem

Give an agent a database and a document store and it will happily answer
from all of them. But a compensation table is not a public wiki: the same
question asked by an analyst, a manager, or the employee themselves should
reach different data. Governance has to happen *before* retrieval, not as
a filter on the way out.

## What this builds

- **Source registry** — structured (SQLite: sales, inventory, compensation)
  and unstructured (policy docs, meeting notes, board minutes) sources,
  each declaring owner, sensitivity, and permitted modes.
- **Personal vs company modes** — personal mode sees only the user's own
  data plus public sources; company mode sees shared sources gated by role.
- **Deny-first routing** — the planner scores sources by relevance, then
  the access policy removes denied ones *before* any query runs. The
  retriever never touches a denied source.
- **Three delivery formats** — `chat` (summary with citations), `table`
  (dashboard rows), `report` (structured report shape).
- **Hash-chained access ledger** — every request logs role, mode,
  allowed/denied sources, and queries run.

All data is synthetic and fictional.

## Quickstart

```python
from govdata import build_registry, route_request, execute_plan, deliver, AccessLedger

reg = build_registry()
ledger = AccessLedger()

plan = route_request("What is total Q3 revenue by region?", role="analyst", mode="company")
result = execute_plan(plan, reg)
print(deliver(plan, result, fmt="chat"))
ledger.log(plan, result)
```

## Same question, different scope

```python
# Personal mode: sales is company/internal -> denied before retrieval
plan = route_request("What is total Q3 revenue by region?", role="analyst", mode="personal")
plan.allowed_names   # [] — sales denied; other sources don't match the question
plan.denied          # sales -> POL-MODE-01, compensation -> POL-MODE-01, ...
```

## Production path

- Replace SQLite with the real warehouse and the doc store with a vector DB.
- Bind roles to OIDC claims instead of string literals.
- Keep the deny-first shape: policy evaluation must stay ahead of retrieval.

## Tests

```bash
pytest -q
```

34 tests, deterministic, no network or API keys.
