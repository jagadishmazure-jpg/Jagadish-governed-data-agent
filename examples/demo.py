"""Same questions, different roles and modes: governance decides before any data is read (offline)."""
from govdata import AccessLedger, build_registry, deliver, execute_plan, route_request

reg = build_registry()
ledger = AccessLedger()
asks = [
    ("What is total Q3 revenue by region?", "analyst", "company"),
    ("What is total Q3 revenue by region?", "analyst", "personal"),
    ("What is the average salary by department?", "analyst", "company"),
    ("What is the average salary by department?", "manager", "company"),
    ("What does the travel policy say about expenses?", "analyst", "company"),
]
for question, role, mode in asks:
    plan = route_request(question, role=role, mode=mode, registry=reg)
    result = execute_plan(plan, reg)
    ledger.log(plan, result)
    print(f"[{role}/{mode}] {question}")
    print(f"  allowed sources: {plan.allowed_names or '-'}")
    for d in plan.denied:
        print(f"  denied {d.name}: {d.rule}")
    for line in deliver(plan, result, fmt="chat").splitlines()[1:5]:
        print("  |", line)
    print()
print(f"Access ledger: {len(ledger.entries)} entries, chain verifies: {ledger.verify_chain()}")
