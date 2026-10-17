# Implementation guide: from offline build to Azure

> Status: **planned**. Nothing here has been deployed. The offline build in this
> repository is what exists today; this guide is how it would be taken to a
> real Azure environment.

## Azure service mapping

| Offline component | Azure service (planned) | Notes |
|---|---|---|
| Role and user ID | Entra ID token: group claims to role, oid to user | Validated at API Management |
| Source registry sensitivity | Microsoft Purview sensitivity labels and data map | Single source of truth |
| SQLite tables | Azure SQL Database or Fabric Warehouse with read-only identity | Row-level security as a second layer |
| Documents | Azure AI Search with security trimming on group IDs |  |
| Access ledger | Log Analytics custom table or immutable blob | Audit and review |

## Steps

1. Take role and user ID from validated Entra ID tokens instead of parameters.
2. Generate the source registry from Purview labels and owners.
3. Keep the router and policy unchanged; they decide before any connector is called.
4. Add row-level security in the database and security trimming in AI Search as defence in depth.
5. Ship the ledger to Log Analytics and review denials weekly with data owners.

## Guardrails to keep when going live

- Deny-first: policy runs before retrieval and the retriever only receives allowed sources.
- Every allow and deny decision cites a stable rule ID and reason.
- Confidential sources need manager or above in company mode.
- Personal mode is limited to the user's own data and public sources.
- Every request is logged with role, mode, allowed and denied sources and queries run, on a hash-chained ledger.

## What to measure before calling it production-ready

- Zero retrievals from denied sources in a red-team suite.
- Answer usefulness for allowed requests.
- Denial rate by role, reviewed with data owners.
