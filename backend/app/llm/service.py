"""Resolve the organisation's default connector and make governed, metered calls through it."""
import os
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import LLMConnector, Organisation, UsageEvent
from ..security import decrypt_json, encrypt_json
from .base import ChatResult, LLMError
from .catalog import provider


class NoModel(LLMError):
    pass


class LLM:
    """A bound model: one connector + one model, recording usage for every call."""

    def __init__(self, db: Session, conn: LLMConnector, org_id: str | None = None):
        self.db, self.conn = db, conn
        self.org_id = org_id or conn.org_id  # usage is metered to the business that made the call
        self.provider = provider(conn.provider, conn.config, decrypt_json(conn.secret_enc))
        self.model = conn.model

    def chat(self, system: str, messages: list, tools=None, purpose="chat", max_tokens=8000) -> ChatResult:
        t0 = time.time()
        ok = True
        try:
            r = self.provider.chat(self.model, system, messages, tools, max_tokens)
            return r
        except LLMError:
            ok = False
            raise
        finally:
            ms = int((time.time() - t0) * 1000)
            r_ = locals().get("r")
            self.db.add(UsageEvent(org_id=self.org_id, connector_id=self.conn.id, provider=self.conn.provider, model=self.model,
                                   purpose=purpose, input_tokens=getattr(r_, "input_tokens", 0) or 0,
                                   output_tokens=getattr(r_, "output_tokens", 0) or 0, latency_ms=ms, ok=ok))
            self.db.commit()


def resolve(db: Session, org_id: str) -> tuple[LLMConnector | None, Organisation | None]:
    """The connector this business runs on: its own default, or, for businesses in a model-sharing group, the default of
    another business in the same group. Groups are set server-side only (for example by the demo seeder), never by a
    request, so one tenant can never borrow another tenant's key. The key itself never leaves the server either way."""
    own = db.execute(select(LLMConnector).where(LLMConnector.org_id == org_id, LLMConnector.is_default.is_(True))).scalar()
    if own:
        return own, None
    org = db.get(Organisation, org_id)
    group = ((org.settings or {}).get("model_group") if org else None)
    if not group:
        return platform_connector(), None
    for o in db.execute(select(Organisation).where(Organisation.id != org_id).order_by(Organisation.created_at)).scalars():
        if (o.settings or {}).get("model_group") != group:
            continue
        c = db.execute(select(LLMConnector).where(LLMConnector.org_id == o.id, LLMConnector.is_default.is_(True))).scalar()
        if c and c.model:
            return c, o
    return platform_connector(), None


def platform_connector() -> LLMConnector | None:
    """The platform-wide model, set only on the server (environment), never in the app: ARIAX_LLM_API_KEY, and optionally
    ARIAX_LLM_PROVIDER (default anthropic) and ARIAX_LLM_MODEL (default claude-opus-5-5). Used by any business without a
    model of its own. The key stays in the server's environment and is encrypted only in memory for the provider."""
    key = os.environ.get("ARIAX_LLM_API_KEY", "").strip()
    if not key:
        return None
    c = LLMConnector(id="platform", org_id="", name="Platform model", provider=os.environ.get("ARIAX_LLM_PROVIDER", "anthropic"),
                     config={}, model=os.environ.get("ARIAX_LLM_MODEL", "claude-opus-5-5"), is_default=True, status="ok", secret_hint="")
    c.secret_enc = encrypt_json({"api_key": key})
    return c


def default_llm(db: Session, org_id: str) -> LLM:
    c, _ = resolve(db, org_id)
    if not c:
        raise NoModel("No AI model is configured for this platform yet. The AI model is set on the server by your administrator.")
    if not c.model:
        raise NoModel(f"The default connector '{c.name}' has no model selected.")
    return LLM(db, c, org_id)


def run_test(prov, model: str) -> dict:
    """A real round trip. Returns a UI-ready result for success or failure."""
    t0 = time.time()
    try:
        r = prov.chat(model, "You are a connectivity check. Reply in one short sentence.",
                      [{"role": "user", "content": "Reply with: Aria XAI connection OK."}], None, 200)
        return {"ok": True, "latency_ms": int((time.time() - t0) * 1000), "reply": (r.text or "(empty reply)")[:300],
                "model": r.model or model, "tokens": {"input": r.input_tokens, "output": r.output_tokens}}
    except LLMError as ex:
        return {"ok": False, "latency_ms": int((time.time() - t0) * 1000), "error": str(ex), "model": model}
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "latency_ms": int((time.time() - t0) * 1000), "error": f"{type(ex).__name__}: {str(ex)[:300]}", "model": model}
