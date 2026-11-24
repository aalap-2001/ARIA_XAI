"""Agent team conversations, streamed as Server-Sent Events (trace events, then the final answer)."""
import json
import queue
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import studio
from ..agents import ANALYST, EXECUTOR, run_turn
from ..db import SessionLocal, get_db
from ..deps import require
from ..models import Blueprint, Conversation, Message, Organisation
from ..rbac import Access

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/team")
def team(a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    bp = db.execute(select(Blueprint).where(Blueprint.org_id == a.org_id, Blueprint.status == "published")).scalar()
    content = bp.content if bp else {}
    view = lambda g: {"id": g["id"], "name": g["name"], "purpose": g["purpose"], "tools": g.get("tools", []), "actions": g.get("actions", [])}  # noqa: E731
    return {"published": bool(bp), "version": bp.version if bp else None, "summary": content.get("summary"),
            "industry": content.get("industry"), "starter_questions": content.get("starter_questions", []),
            "leads": [view(g) for g in (ANALYST, EXECUTOR) if a.can_use_agent(g["id"])],
            "agents": [view(g) for g in content.get("agents") or [] if a.can_use_agent(g["id"])],
            "watch": {"rules": len(content.get("watch_rules") or [])}, "persona": studio.persona(db.get(Organisation, a.org_id))}


def _conv(db, a: Access, cid) -> Conversation:
    c = db.get(Conversation, cid)
    if not c or c.org_id != a.org_id or (c.user_id != a.actor_id and c.channel == "console"):
        raise HTTPException(404, "Conversation not found")
    return c


@router.get("/conversations")
def list_convs(a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    rows = db.execute(select(Conversation).where(Conversation.org_id == a.org_id, Conversation.user_id == a.actor_id)
                      .order_by(Conversation.updated_at.desc()).limit(100)).scalars().all()
    return [{"id": c.id, "title": c.title, "updated_at": c.updated_at} for c in rows]


@router.post("/conversations")
def new_conv(a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    c = Conversation(org_id=a.org_id, user_id=a.actor_id)
    db.add(c)
    db.commit()
    return {"id": c.id, "title": c.title}


@router.get("/conversations/{cid}")
def get_conv(cid: str, a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    c = _conv(db, a, cid)
    msgs = db.execute(select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at)).scalars().all()
    return {"id": c.id, "title": c.title, "messages": [{"id": m.id, "role": m.role, "content": m.content, "trace": m.trace, "created_at": m.created_at} for m in msgs]}


@router.delete("/conversations/{cid}")
def del_conv(cid: str, a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    c = _conv(db, a, cid)
    db.delete(c)
    db.commit()
    return {"ok": True}


class Say(BaseModel):
    message: str = Field(min_length=1, max_length=20000)


def run_and_store(org_access: Access, conv_id: str, message: str, emit, channel: str = "console") -> dict:
    """Shared by the console, the public API and the widget."""
    db = SessionLocal()
    try:
        c = db.get(Conversation, conv_id)
        hist = [{"role": m.role, "content": m.content} for m in
                db.execute(select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)).scalars()]
        db.add(Message(conversation_id=conv_id, role="user", content=message))
        if c.title == "New conversation":
            c.title = message[:80]
        db.commit()
        trace = []

        def collect(evt):
            trace.append(evt)
            emit(evt)
        out = run_turn(db, org_access, conv_id, message, hist, collect, channel)
        m = Message(conversation_id=conv_id, role="assistant", content=out["text"], trace=trace)
        db.add(m)
        c.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"message_id": m.id, "text": out["text"], "decisions": out.get("decisions", []), "plans": out.get("plans", []), "trace": trace}
    finally:
        db.close()


@router.post("/conversations/{cid}/messages")
def send(cid: str, body: Say, a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    _conv(db, a, cid)
    q: queue.Queue = queue.Queue()

    def work():
        try:
            res = run_and_store(a, cid, body.message, lambda e: q.put(("trace", e)))
            q.put(("final", res))
        except Exception as ex:  # noqa: BLE001
            q.put(("final", {"text": f"⚠ {type(ex).__name__}: {ex}", "decisions": [], "error": True}))
        q.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while True:
            try:
                item = q.get(timeout=15)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if item is None:
                break
            kind, data = item
            if kind == "final":
                data = {k: v for k, v in data.items() if k != "trace"}
            yield f"event: {kind}\ndata: {json.dumps(data, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ history: every conversation with the agent team, by user
@router.get("/history")
def history(user_id: str | None = None, channel: str | None = None, a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    """Your own conversations; with Audit permission, anyone's (including API and widget conversations)."""
    from sqlalchemy import func

    from ..models import Membership, User
    auditor = a.can("audit:view")
    q = select(Conversation).where(Conversation.org_id == a.org_id)
    if not auditor:
        q = q.where(Conversation.user_id == a.actor_id)
    else:
        if user_id:
            q = q.where(Conversation.user_id == user_id)
        if channel:
            q = q.where(Conversation.channel == channel)
    rows = db.execute(q.order_by(Conversation.updated_at.desc()).limit(300)).scalars().all()
    counts = dict(db.execute(select(Message.conversation_id, func.count()).where(Message.conversation_id.in_([c.id for c in rows]))
                             .group_by(Message.conversation_id)).all()) if rows else {}
    users = {u.id: u for u in db.execute(select(User).where(User.id.in_({c.user_id for c in rows if c.user_id}))).scalars()} if rows else {}
    out = {"conversations": [{"id": c.id, "title": c.title, "channel": c.channel, "end_user_id": c.end_user_id, "messages": counts.get(c.id, 0),
                              "user": ({"id": c.user_id, "name": users[c.user_id].name, "email": users[c.user_id].email} if c.user_id in users else None),
                              "created_at": c.created_at, "updated_at": c.updated_at} for c in rows],
           "can_see_everyone": auditor}
    if auditor:
        out["users"] = [{"id": m.user.id, "name": m.user.name, "email": m.user.email}
                        for m in db.execute(select(Membership).where(Membership.org_id == a.org_id)).scalars()]
    return out


@router.get("/history/{cid}")
def history_conversation(cid: str, a: Access = Depends(require("chat:use")), db: Session = Depends(get_db)):
    from ..models import Plan, User
    c = db.get(Conversation, cid)
    if not c or c.org_id != a.org_id or (c.user_id != a.actor_id and not a.can("audit:view")):
        raise HTTPException(404, "Conversation not found")
    u = db.get(User, c.user_id) if c.user_id else None
    msgs = db.execute(select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at)).scalars().all()
    plans = db.execute(select(Plan).where(Plan.conversation_id == c.id).order_by(Plan.created_at)).scalars().all()
    return {"id": c.id, "title": c.title, "channel": c.channel, "end_user_id": c.end_user_id, "created_at": c.created_at,
            "user": {"id": u.id, "name": u.name, "email": u.email} if u else None,
            "messages": [{"id": m.id, "role": m.role, "content": m.content, "trace": m.trace, "created_at": m.created_at} for m in msgs],
            "plans": [{"id": p.id, "title": p.title, "status": p.status, "accountable": p.accountable} for p in plans]}
