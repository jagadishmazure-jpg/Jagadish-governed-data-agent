# Governance model

## Modes

| Mode | Sees |
|------|------|
| `personal` | Only sources owned by the requester, plus `public` sources |
| `company` | Shared sources, gated by role and sensitivity |

A source also declares `mode_allow` (`personal` / `company` / `both`), so a
source can opt out of a mode entirely (e.g. `sales` is `company`-only).

## RBAC matrix (company mode)

| Sensitivity | analyst | manager | admin |
|-------------|---------|---------|-------|
| public | ✅ | ✅ | ✅ |
| internal | ✅ | ✅ | ✅ |
| confidential | ❌ | ✅ | ✅ |

Rule IDs (stable, appear in denials and the audit ledger):

- `POL-MODE-01` — the source's `mode_allow` excludes the request mode.
- `POL-PERS-02` — personal mode: source is neither public nor owned by the user.
- `POL-ROLE-03` — company mode: role below the sensitivity floor.
- `POL-ALLOW-00` — access granted (logged with its reason).

## Deny-first design

1. The router scores sources by keyword overlap with the question.
2. The policy evaluates *every* source — candidates and non-candidates —
   so denials are explicit in the audit trail.
3. `execute_plan` only iterates `plan.planned`. Denied sources are never
   queried, never read, never leaked into prompts.

This mirrors how employee access works: you don't get to see the file and
then have it redacted — you never get the file.
