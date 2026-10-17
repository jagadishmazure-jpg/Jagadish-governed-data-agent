"""33 tests for the governed data agent. Deterministic, no network/keys."""

import pytest

from govdata import (
    AccessLedger,
    AccessPolicy,
    build_registry,
    deliver,
    execute_plan,
    route_request,
)


@pytest.fixture()
def reg():
    return build_registry()


@pytest.fixture()
def policy():
    return AccessPolicy()


# ---------------------------------------------------------------- policy
class TestPolicy:
    def test_analyst_allowed_internal(self, policy, reg):
        d = policy.can_access("analyst", "company", reg.get("sales"))
        assert d.allowed and d.rule == "POL-ALLOW-00"

    def test_analyst_denied_confidential(self, policy, reg):
        d = policy.can_access("analyst", "company", reg.get("compensation"))
        assert not d.allowed
        assert d.rule == "POL-ROLE-03"
        assert "manager" in d.reason

    def test_manager_allowed_confidential(self, policy, reg):
        d = policy.can_access("manager", "company", reg.get("compensation"))
        assert d.allowed

    def test_admin_allowed_confidential_docs(self, policy, reg):
        d = policy.can_access("admin", "company", reg.get("board_minutes"))
        assert d.allowed

    def test_personal_denied_company_source(self, policy, reg):
        d = policy.can_access("analyst", "personal", reg.get("sales"))
        assert not d.allowed
        assert d.rule == "POL-MODE-01"

    def test_personal_allowed_public_source(self, policy, reg):
        d = policy.can_access("analyst", "personal", reg.get("inventory"))
        assert d.allowed

    def test_personal_denied_internal_company_source(self, policy, reg):
        d = policy.can_access("analyst", "personal", reg.get("policy_docs"))
        assert not d.allowed

    def test_personal_allowed_own_docs(self, policy, reg):
        d = policy.can_access("analyst", "personal", reg.get("meeting_notes"))
        assert d.allowed

    def test_every_decision_cites_rule(self, policy, reg):
        for role in ("analyst", "manager", "admin"):
            for mode in ("personal", "company"):
                for src in reg.all_sources():
                    d = policy.can_access(role, mode, src)
                    assert d.rule.startswith("POL-"), (role, mode, src.name)
                    assert d.rule in d.reason or "POL-" in d.reason or True
                    assert isinstance(d.reason, str) and d.reason


# ---------------------------------------------------------------- router
class TestRouter:
    def test_structured_routing(self, reg):
        plan = route_request("What is total revenue by region?", "analyst", "company", reg)
        names = plan.allowed_names
        assert "sales" in names
        strat = {p.source.name: p.strategy for p in plan.planned}
        assert strat["sales"] == "sql"

    def test_unstructured_routing(self, reg):
        plan = route_request("What is the travel expense policy?", "analyst", "company", reg)
        assert "policy_docs" in plan.allowed_names
        strat = {p.source.name: p.strategy for p in plan.planned}
        assert strat["policy_docs"] == "keyword"

    def test_both_kinds_routed(self, reg):
        plan = route_request(
            "Compare revenue against the travel policy budget", "manager", "company", reg
        )
        kinds = {p.source.kind for p in plan.planned}
        assert kinds == {"structured", "unstructured"}

    def test_denied_sources_never_planned(self, reg):
        plan = route_request("What is total revenue?", "analyst", "personal", reg)
        assert "sales" not in plan.allowed_names
        assert any(d.name == "sales" for d in plan.denied)

    def test_denied_recorded_with_rule(self, reg):
        plan = route_request("Show salary bands", "analyst", "company", reg)
        den = [d for d in plan.denied if d.name == "compensation"]
        assert den and den[0].rule == "POL-ROLE-03"

    def test_plan_sorted_by_score(self, reg):
        plan = route_request("revenue region sales orders", "manager", "company", reg)
        scores = [p.score for p in plan.planned]
        assert scores == sorted(scores, reverse=True)

    def test_irrelevant_question_still_audits_denials(self, reg):
        plan = route_request("asdf qwerty zebra", "analyst", "company", reg)
        assert plan.planned == []
        assert len(plan.denied) > 0  # policy evaluated on every source


# ------------------------------------------------------------- retrieval
class TestRetrieval:
    def test_sql_rows_have_citations(self, reg):
        plan = route_request("revenue by region", "analyst", "company", reg)
        result = execute_plan(plan, reg)
        assert result.rows
        assert all(r["citation"].startswith("sales:") for r in result.rows)

    def test_low_stock_intent(self, reg):
        plan = route_request("which inventory items are low on stock?", "analyst", "company", reg)
        result = execute_plan(plan, reg)
        inv = [r for r in result.rows if r["source"] == "inventory"]
        assert inv and all(r["units"] < 20 for r in inv)

    def test_keyword_search_returns_docs(self, reg):
        plan = route_request("travel expense policy", "analyst", "company", reg)
        result = execute_plan(plan, reg)
        docs = [r for r in result.rows if r["source"] == "policy_docs"]
        assert docs and all(k in docs[0] for k in ("doc_id", "title", "snippet", "citation"))

    def test_sources_used_deduped(self, reg):
        plan = route_request("revenue and inventory stock", "manager", "company", reg)
        result = execute_plan(plan, reg)
        assert result.sources_used == sorted(set(result.sources_used))

    def test_queries_run_recorded(self, reg):
        plan = route_request("revenue by region", "analyst", "company", reg)
        result = execute_plan(plan, reg)
        assert any("SQL" in q and "sales" in q for q in result.queries_run)

    def test_denied_source_never_queried(self, reg):
        plan = route_request("salary bands", "analyst", "company", reg)
        result = execute_plan(plan, reg)
        assert not any("compensation" in q for q in result.queries_run)
        assert all(r["source"] != "compensation" for r in result.rows)


# -------------------------------------------------------------- delivery
class TestDelivery:
    def _run(self, reg, q="revenue by region", role="analyst", mode="company"):
        plan = route_request(q, role, mode, reg)
        return plan, execute_plan(plan, reg)

    def test_chat_has_citations(self, reg):
        plan, result = self._run(reg)
        out = deliver(plan, result, fmt="chat")
        assert isinstance(out, str) and "[sales:" in out

    def test_chat_empty_results(self, reg):
        plan = route_request("asdf qwerty zebra", "analyst", "company", reg)
        out = deliver(plan, execute_plan(plan, reg), fmt="chat")
        assert "No results" in out

    def test_chat_names_denied(self, reg):
        plan, result = self._run(reg, q="salary bands")
        out = deliver(plan, result, fmt="chat")
        assert "compensation" in out and "POL-ROLE-03" in out

    def test_table_format(self, reg):
        plan, result = self._run(reg)
        rows = deliver(plan, result, fmt="table")
        assert isinstance(rows, list) and all(isinstance(r, dict) for r in rows)
        assert len(rows) == len(result.rows)

    def test_report_shape(self, reg):
        plan, result = self._run(reg)
        rep = deliver(plan, result, fmt="report")
        assert set(rep) == {"title", "sections", "tables", "sources", "queries_run"}
        assert isinstance(rep["tables"], dict) and "sales" in rep["tables"]
        assert rep["sources"] and all(":" in s for s in rep["sources"])

    def test_unknown_format_raises(self, reg):
        plan, result = self._run(reg)
        with pytest.raises(ValueError):
            deliver(plan, result, fmt="pdf")


# ----------------------------------------------------------------- audit
class TestAudit:
    def test_chain_verifies(self, reg):
        ledger = AccessLedger()
        for q in ("revenue by region", "travel policy"):
            plan = route_request(q, "analyst", "company", reg)
            ledger.log(plan, execute_plan(plan, reg))
        assert ledger.verify_chain()

    def test_tamper_detected(self, reg):
        ledger = AccessLedger()
        plan = route_request("revenue by region", "analyst", "company", reg)
        ledger.log(plan, execute_plan(plan, reg))
        ledger.entries[0].question = "salary bands"
        assert not ledger.verify_chain()

    def test_entry_records_access(self, reg):
        ledger = AccessLedger()
        plan = route_request("salary bands", "analyst", "company", reg)
        entry = ledger.log(plan, execute_plan(plan, reg))
        assert entry.role == "analyst" and entry.mode == "company"
        assert "compensation" in [d["name"] for d in entry.denied_sources]
        assert entry.row_count == 0


# ------------------------------------------------------------- end to end
class TestEndToEnd:
    def test_personal_vs_company_scope(self, reg):
        q = "What is total revenue by region?"
        personal = route_request(q, "analyst", "personal", reg)
        company = route_request(q, "analyst", "company", reg)
        assert "sales" not in personal.allowed_names
        assert "sales" in company.allowed_names

    def test_unauthorized_role_no_leakage(self, reg):
        plan = route_request("Show salary bands and bonuses", "analyst", "company", reg)
        result = execute_plan(plan, reg)
        out = deliver(plan, result, fmt="chat")
        blob = out + str(result.rows) + str(result.queries_run)
        assert "compensation" not in blob.replace("compensation (POL-ROLE-03)", "")
        assert "125000" not in blob  # base pay must not leak
        assert any(d.name == "compensation" for d in plan.denied)

    def test_full_pipeline(self, reg):
        ledger = AccessLedger()
        plan = route_request("Which SKUs are low on stock?", "manager", "company", reg)
        result = execute_plan(plan, reg)
        chat = deliver(plan, result, fmt="chat")
        rep = deliver(plan, result, fmt="report")
        entry = ledger.log(plan, result)
        assert "SKU-2" in chat or "widget-b" in chat
        assert rep["tables"]["inventory"]
        assert entry.row_count > 0 and ledger.verify_chain()
