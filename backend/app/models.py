"""Data model. Every tenant-owned row carries org_id; every query filters on it."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def uid(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:20]


def now() -> datetime:
    return datetime.now(timezone.utc)


class Organisation(Base):
    __tablename__ = "organisations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("org_"))
    name: Mapped[str] = mapped_column(String(200))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    product_description: Mapped[str] = mapped_column(Text, default="")
    webhook_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("usr_"))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)  # optional sign-in name, lower case
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("org_id", "name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("rol_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    permissions: Mapped[list] = mapped_column(JSON, default=list)   # ["users:view", "*", ...]
    scopes: Mapped[dict] = mapped_column(JSON, default=dict)        # agents, data, actions, approval_limit


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("mem_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | deactivated
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    user: Mapped[User] = relationship(lazy="joined")
    role: Mapped[Role] = relationship(lazy="joined")


class Invite(Base):
    __tablename__ = "invites"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("inv_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256 of the cookie token
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"))
    csrf: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str] = mapped_column(String(64), default="")


class LLMConnector(Base):
    __tablename__ = "llm_connectors"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("llm_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(40))
    config: Mapped[dict] = mapped_column(JSON, default=dict)        # non-secret fields
    secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret_hint: Mapped[str] = mapped_column(String(20), default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="untested")  # untested | ok | failed
    last_test: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DataConnection(Base):
    __tablename__ = "data_connections"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("dc_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))   # postgres | mysql | mssql | sqlite | rest | upload
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="new")
    error: Mapped[str] = mapped_column(Text, default="")
    introspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("doc_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(400))
    mime: Mapped[str] = mapped_column(String(120), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64))
    pages: Mapped[int] = mapped_column(Integer, default=0)
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    error: Mapped[str] = mapped_column(Text, default="")
    uploaded_by: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("chk_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    ord: Mapped[int] = mapped_column(Integer)
    page: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)
    terms: Mapped[dict] = mapped_column(JSON, default=dict)


class Blueprint(Base):
    __tablename__ = "blueprints"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("bp_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # generating | failed | draft | published | archived
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    progress: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[dict] = mapped_column(JSON, default=dict)
    # who created or last changed each record: {section: {key: {"kind": "human", "by": name, "at": iso, "change": ...}}};
    # records missing here were generated by Aria XAI
    provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    published_by: Mapped[str] = mapped_column(String(32), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("cv_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), default="console")  # console | api | widget
    end_user_id: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(300), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("msg_"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    trace: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("dcs_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    blueprint_version: Mapped[int] = mapped_column(Integer, default=0)
    agent: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    risk: Mapped[str] = mapped_column(String(10))
    summary: Mapped[str] = mapped_column(Text, default="")
    facts: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64))
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[str] = mapped_column(String(30))
    explanation: Mapped[dict] = mapped_column(JSON, default=dict)
    effect: Mapped[str] = mapped_column(String(10))       # ALLOW | REVIEW | BLOCK
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20))       # EXECUTED | PENDING_REVIEW | BLOCKED | REJECTED | FAILED
    requested_by: Mapped[str] = mapped_column(String(200), default="")
    # The human accountable for this action (the person who approved the plan), never the AI.
    accountable: Mapped[str | None] = mapped_column(String(320), nullable=True)
    owner_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    reviewer: Mapped[str] = mapped_column(String(200), default="")
    review_note: Mapped[str] = mapped_column(Text, default="")
    execution: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Plan(Base):
    """A write plan proposed by Aria Executor. Nothing runs until the responsible human approves it."""
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("pl_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="chat")      # chat | api | widget | watch
    suggestion_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[list] = mapped_column(JSON, default=list)
    approver_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # who must approve (chat)
    owner_role: Mapped[str | None] = mapped_column(String(100), nullable=True)       # or: members of this role
    status: Mapped[str] = mapped_column(String(20), default="awaiting_approval")
    accountable: Mapped[str | None] = mapped_column(String(320), nullable=True)
    results: Mapped[list] = mapped_column(JSON, default=list)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Event(Base):
    """Activity reported by the customer's product through the Events API."""
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("ev_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(120), index=True)
    entity_id: Mapped[str] = mapped_column(String(200), default="")
    actor: Mapped[dict] = mapped_column(JSON, default=dict)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[str] = mapped_column(String(40), default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    status: Mapped[str] = mapped_column(String(20), default="received")  # received|ignored|investigating|no_action|suggested|failed
    matched_rule: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    trace: Mapped[list] = mapped_column(JSON, default=list)
    suggestion_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Suggestion(Base):
    """An improvement Aria Watch proposes. The area's owner approves; then Aria Executor carries it out."""
    __tablename__ = "suggestions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("sg_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    rationale: Mapped[str] = mapped_column(Text, default="")
    benefit: Mapped[str] = mapped_column(Text, default="")
    owner_role: Mapped[str] = mapped_column(String(100), default="")
    steps: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending")   # pending | approved | rejected | executed | failed
    decided_by: Mapped[str] = mapped_column(String(320), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    plan_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EgressLog(Base):
    """Every outbound send, written by the egress path itself. The watchdog reconciles it against decisions."""
    __tablename__ = "egress_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(32), index=True)
    decision_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    executor: Mapped[str] = mapped_column(String(20))      # webhook | database
    target: Mapped[str] = mapped_column(String(500))
    payload_hash: Mapped[str] = mapped_column(String(64))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEntry(Base):
    __tablename__ = "audit"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(32), index=True)
    at: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(320))
    kind: Mapped[str] = mapped_column(String(60))
    target: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uid("key_"))
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))  # secret | publishable
    prefix: Mapped[str] = mapped_column(String(24))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"))
    allowed_origins: Mapped[list] = mapped_column(JSON, default=list)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageEvent(Base):
    __tablename__ = "usage_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String(32), index=True)
    connector_id: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(String(60))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
