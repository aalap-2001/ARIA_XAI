"""Put the agent team inside the customer's own product: a server API and an embeddable widget."""
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import BASE_URL
from ..db import get_db
from ..deps import api_key_access
from ..models import Conversation
from .chat import run_and_store

router = APIRouter(tags=["public"])


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: str | None = None
    end_user_id: str = Field(default="", max_length=200)


def _chat(db, access, body: ChatIn, channel: str):
    conv = db.get(Conversation, body.conversation_id) if body.conversation_id else None
    if conv and (conv.org_id != access.org_id or conv.channel != channel or conv.end_user_id != body.end_user_id):
        raise HTTPException(404, "Conversation not found")
    if not conv:
        conv = Conversation(org_id=access.org_id, user_id=None, channel=channel, end_user_id=body.end_user_id)
        db.add(conv)
        db.commit()
    res = run_and_store(access, conv.id, body.message, lambda e: None, channel)
    return {"conversation_id": conv.id, "reply": res["text"], "decisions": res["decisions"], "plans": res["plans"]}


class EventIn(BaseModel):
    type: str = Field(min_length=1, max_length=120, description="Dotted event name, e.g. thing.created or thing.updated")
    entity_id: str = Field(default="", max_length=200)
    data: dict = {}
    actor: dict = {}
    occurred_at: str = ""


@router.post("/v1/events", status_code=202)
def v1_events(body: EventIn, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Your product reports activity here. Aria Watch triages every event; only the ones its watch rules
    select are investigated."""
    from ..watch import ingest
    access = api_key_access(db, authorization.removeprefix("Bearer ").strip(), "secret")
    ev = ingest(db, access.org_id, body.model_dump())
    return {"id": ev.id, "status": "received"}


@router.post("/v1/agents/chat")
def v1_chat(body: ChatIn, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Server-to-server. Authorization: Bearer ax_sk_…"""
    access = api_key_access(db, authorization.removeprefix("Bearer ").strip(), "secret")
    return _chat(db, access, body, "api")


@router.options("/v1/widget/chat")
def widget_preflight(request: Request):
    return Response(status_code=204, headers=_cors(request.headers.get("origin")))


@router.post("/v1/widget/chat")
def widget_chat(body: ChatIn, request: Request, x_ariax_key: str = Header(default=""), db: Session = Depends(get_db)):
    origin = request.headers.get("origin")
    access = api_key_access(db, x_ariax_key, "publishable", origin)
    out = _chat(db, access, body, "widget")
    return Response(content=__import__("json").dumps(out, default=str), media_type="application/json", headers=_cors(origin))


def _cors(origin):
    return {"Access-Control-Allow-Origin": origin or "*", "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-AriaX-Key", "Vary": "Origin"}


WIDGET = r"""(function(){
var s=document.currentScript, key=s.getAttribute('data-key'), base=s.src.replace(/\/widget\.js.*$/,''), title=s.getAttribute('data-title')||'Ask our AI team';
var color=s.getAttribute('data-color')||'#0b7a83', uid=s.getAttribute('data-user')||'', ck='ariax_cv_'+key.slice(0,12);
var css='#axw-b{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;background:'+color+';color:#fff;border:0;font:600 22px Inter,\'Segoe UI Variable\',\'Segoe UI\',system-ui,sans-serif;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.2);z-index:2147483000}'+
'#axw-p{position:fixed;right:20px;bottom:88px;width:min(380px,calc(100vw - 40px));height:min(560px,calc(100vh - 120px));background:#fff;border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.2);display:none;flex-direction:column;overflow:hidden;z-index:2147483000;font:14px/1.45 Inter,\'Segoe UI Variable\',\'Segoe UI\',system-ui,sans-serif;color:#111}'+
'#axw-h{padding:14px 16px;background:'+color+';color:#fff;font-weight:600}#axw-m{flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f7f7f9}'+
'.axw-u,.axw-a{max-width:85%;padding:8px 12px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word}.axw-u{align-self:flex-end;background:'+color+';color:#fff}.axw-a{align-self:flex-start;background:#fff;border:1px solid #e5e5ea}'+
'#axw-f{display:flex;gap:6px;padding:10px;border-top:1px solid #eee}#axw-i{flex:1;border:1px solid #ddd;border-radius:8px;padding:8px}#axw-s{background:'+color+';color:#fff;border:0;border-radius:8px;padding:0 14px;cursor:pointer}';
var st=document.createElement('style');st.textContent=css;document.head.appendChild(st);
var b=document.createElement('button');b.id='axw-b';b.textContent='✦';b.setAttribute('aria-label',title);
var p=document.createElement('div');p.id='axw-p';p.innerHTML='<div id="axw-h"></div><div id="axw-m"></div><form id="axw-f"><input id="axw-i" placeholder="Type a message…" autocomplete="off"><button id="axw-s">Send</button></form>';
document.body.appendChild(b);document.body.appendChild(p);p.querySelector('#axw-h').textContent=title;
var m=p.querySelector('#axw-m'),f=p.querySelector('#axw-f'),i=p.querySelector('#axw-i');
function add(c,t){var d=document.createElement('div');d.className=c;d.textContent=t;m.appendChild(d);m.scrollTop=m.scrollHeight;return d}
b.onclick=function(){p.style.display=p.style.display==='flex'?'none':'flex';if(p.style.display==='flex')i.focus()};
f.onsubmit=function(e){e.preventDefault();var t=i.value.trim();if(!t)return;i.value='';add('axw-u',t);var w=add('axw-a','…');
var cv=null;try{cv=localStorage.getItem(ck)}catch(_){}
fetch(base+'/v1/widget/chat',{method:'POST',headers:{'Content-Type':'application/json','X-AriaX-Key':key},body:JSON.stringify({message:t,conversation_id:cv,end_user_id:uid})})
.then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.detail||r.statusText);return j})})
.then(function(j){w.textContent=j.reply;try{localStorage.setItem(ck,j.conversation_id)}catch(_){}})
.catch(function(err){w.textContent='Sorry, '+err.message})}
})();"""


@router.get("/widget.js")
def widget_js():
    return Response(content=WIDGET, media_type="application/javascript", headers={"Cache-Control": "public, max-age=300"})


@router.get("/api/embed-snippet")
def snippet(key_prefix: str = "ax_pk_…"):
    return {"html": f'<script src="{BASE_URL}/widget.js" data-key="{key_prefix}" data-title="Ask our AI team" async></script>',
            "curl": f"curl -X POST {BASE_URL}/v1/agents/chat -H \"Authorization: Bearer ax_sk_…\" -H \"Content-Type: application/json\" "
                    "-d '{\"message\": \"Hello\", \"end_user_id\": \"user-123\"}'"}
