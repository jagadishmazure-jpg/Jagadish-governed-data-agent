"""Access policy: RBAC x personal/company modes, deny-first.

Personal mode  = the user's own data + public sources only.
Company mode   = shared sources, gated by role and sensitivity.
Confidential sources require manager or above, in either mode.
Every decision cites the rule that produced it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

from govdata.sources import Source

Role = Literal["analyst", "manager", "admin"]
Mode = Literal["personal", "company"]

# Rule IDs are part of the audit trail; keep them stable.
_RULE_MODE = "POL-MODE-01"      # mode must permit the source
_RULE_PERSONAL = "POL-PERS-02"  # personal mode: own data + public only
_RULE_ROLE = "POL-ROLE-03"      # company mode: role must clear sensitivity
_ALLOW = "POL-ALLOW-00"

# Company-mode sensitivity floor: minimum role index per sensitivity.
_ROLE_RANK = {"analyst": 0, "manager": 1, "admin": 2}
_SENSITIVITY_MIN_ROLE = {"public": 0, "internal": 0, "confidential": 1}


@dataclass(frozen=True)
class Decision:
    allowed: bool
    rule: str
    reason: str


class AccessPolicy:
    """Stateless policy evaluator."""

    def can_access(
        self,
        role: Role,
        mode: Mode,
        source: Source,
        user_id: str = "a.chen",
    ) -> Decision:
        """Decide access for (role, mode, source); always cites a rule."""
        if source.mode_allow != "both" and source.mode_allow != mode:
            return Decision(
                allowed=False,
                rule=_RULE_MODE,
                reason=(
                    f"denied: mode '{mode}' does not permit source '{source.name}' "
                    f"(mode_allow='{source.mode_allow}')"
                ),
            )

        if mode == "personal":
            own = source.owner == user_id
            if source.sensitivity == "public" or own:
                return Decision(
                    allowed=True,
                    rule=_ALLOW,
                    reason=(
                        f"allowed: personal mode, source '{source.name}' is "
                        f"{'owned by user' if own else 'public'}"
                    ),
                )
            return Decision(
                allowed=False,
                rule=_RULE_PERSONAL,
                reason=(
                    f"denied: personal mode permits only the user's own data and "
                    f"public sources; '{source.name}' is {source.sensitivity} "
                    f"(owner '{source.owner}')"
                ),
            )

        # company mode: sensitivity gate
        need = _SENSITIVITY_MIN_ROLE[source.sensitivity]
        have = _ROLE_RANK[role]
        if have >= need:
            return Decision(
                allowed=True,
                rule=_ALLOW,
                reason=(
                    f"allowed: company mode, role '{role}' clears "
                    f"{source.sensitivity} source '{source.name}'"
                ),
            )
        min_role = next(r for r, v in _ROLE_RANK.items() if v == need)
        return Decision(
            allowed=False,
            rule=_RULE_ROLE,
            reason=(
                f"denied: role '{role}' insufficient for {source.sensitivity} "
                f"source '{source.name}' (requires '{min_role}' or above)"
            ),
        )
