"""§03.1, One Principal, constructed once at the request edge and threaded through every
subsystem. No subsystem constructs its own (the Fabric's service principal is the one exception,
and it is defined here so it is still one type)."""
from dataclasses import asdict, dataclass, field, replace

from .ids import new_trace_id


@dataclass(frozen=True)
class Principal:
    tenant: str                     # the client organisation
    service: str                    # the product / domain service (e.g. a bundle id), or "fabric"
    agent: str                      # the agent or human role acting
    case: str | None = None         # the unit of work being processed
    on_behalf_of: str | None = None  # end user, if delegated (consent token subject)
    trace_id: str = field(default_factory=new_trace_id)

    def __post_init__(self):
        if not (self.tenant and self.service and self.agent):
            raise ValueError("Principal requires tenant, service and agent")

    def scope_key(self) -> str:
        return f"{self.tenant}:{self.service}:{self.agent}"

    def with_case(self, case: str) -> "Principal":
        return replace(self, case=case)

    def to_dict(self) -> dict:
        return asdict(self)


def fabric_principal(tenant: str) -> Principal:
    """The Fabric's own identity, the only one allowed to resolve governed instances."""
    return Principal(tenant=tenant, service="fabric", agent="fabric")
