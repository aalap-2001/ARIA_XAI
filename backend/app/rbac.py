"""Roles, permissions and scoped access. Enforced server-side on every endpoint."""
from dataclasses import dataclass, field

RESOURCES = {
    "org": ("Organisation settings", ["view", "edit"]),
    "users": ("Users & invitations", ["view", "create", "edit", "delete"]),
    "roles": ("Roles & access", ["view", "create", "edit", "delete"]),
    "llm": ("AI model connectors", ["view", "create", "edit", "delete"]),
    "data": ("Data connections", ["view", "create", "edit", "delete"]),
    "knowledge": ("Knowledge base (documents)", ["view", "create", "delete"]),
    "blueprint": ("Product understanding & blueprint", ["view", "create", "edit", "publish"]),
    "chat": ("Agent team", ["use"]),
    "approvals": ("Approvals", ["view", "approve"]),
    "audit": ("Audit log & decisions", ["view"]),
    "api_keys": ("API keys & widget", ["view", "create", "delete"]),
    "usage": ("Usage", ["view"]),
}
ALL_PERMISSIONS = [f"{r}:{a}" for r, (_, acts) in RESOURCES.items() for a in acts]

FULL_SCOPES = {"agents": ["*"], "data": {"*": ["*"]}, "actions": ["*"], "approval_limit": None}

BUILTIN_ROLES = [
    {"name": "Owner", "description": "Full control of the organisation, including roles and billing-level settings.",
     "permissions": ["*"], "scopes": FULL_SCOPES},
    {"name": "Org admin", "description": "Manages users, roles, data connections and settings.",
     "permissions": [p for p in ALL_PERMISSIONS if p != "roles:delete"], "scopes": FULL_SCOPES},
    {"name": "Builder", "description": "Teaches Aria XAI the product: documents, data, blueprint and agent team.",
     "permissions": ["llm:view", "data:view", "data:create", "data:edit", "knowledge:view", "knowledge:create", "knowledge:delete",
                     "blueprint:view", "blueprint:create", "blueprint:edit", "blueprint:publish", "chat:use", "audit:view", "usage:view"],
     "scopes": FULL_SCOPES},
    {"name": "Reviewer", "description": "Approves or rejects actions the agents escalate.",
     "permissions": ["blueprint:view", "chat:use", "approvals:view", "approvals:approve", "audit:view"],
     "scopes": {"agents": ["*"], "data": {"*": ["*"]}, "actions": ["*"], "approval_limit": None}},
    {"name": "Operator", "description": "Works with the agent team day to day.",
     "permissions": ["chat:use", "approvals:view"],
     "scopes": {"agents": ["*"], "data": {"*": ["*"]}, "actions": ["*"], "approval_limit": 0}},
]


@dataclass
class Access:
    """Resolved permissions + scopes for one principal (a user session or an API key)."""
    org_id: str
    actor_id: str
    actor_label: str
    role_id: str
    role_name: str
    permissions: list = field(default_factory=list)
    scopes: dict = field(default_factory=dict)
    via: str = "session"  # session | api_key | widget

    def can(self, perm: str) -> bool:
        if "*" in self.permissions or perm in self.permissions:
            return True
        res = perm.split(":")[0]
        return f"{res}:*" in self.permissions

    def can_use_agent(self, agent_id: str) -> bool:
        a = self.scopes.get("agents", ["*"])
        return "*" in a or agent_id in a

    def allowed_tables(self, connection_id: str) -> list[str]:
        d = self.scopes.get("data", {"*": ["*"]})
        return d.get(connection_id) or d.get("*") or []

    def can_action(self, action: str) -> bool:
        a = self.scopes.get("actions", ["*"])
        return "*" in a or action in a

    @property
    def approval_limit(self):
        return self.scopes.get("approval_limit")

    def public(self) -> dict:
        return {"role_id": self.role_id, "role": self.role_name, "permissions": self.permissions, "scopes": self.scopes}


def normalise_scopes(s: dict | None) -> dict:
    s = s or {}
    lim = s.get("approval_limit")
    return {"agents": list(s.get("agents") or []), "data": dict(s.get("data") or {}),
            "actions": list(s.get("actions") or []), "approval_limit": None if lim in (None, "") else float(lim)}


def check_permissions(perms: list) -> list:
    bad = [p for p in perms if p != "*" and p not in ALL_PERMISSIONS and not (p.endswith(":*") and p.split(":")[0] in RESOURCES)]
    if bad:
        raise ValueError(f"Unknown permissions: {', '.join(bad)}")
    return sorted(set(perms))
