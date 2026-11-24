"""Aria XAI, turn any product into a governed AI agent team.

Run:  uvicorn app.main:app --port 8700   (from aria-x/backend)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import ROOT
from .config import ENV, PRODUCTION
from .db import init_db
from .routers import admin, auth, chat, data, govern, llm, product, public, studio

@asynccontextmanager
async def lifespan(_app):
    init_db()
    from .watch import start_worker
    start_worker()
    yield


app = FastAPI(title="Aria XAI", version="1.0.0", lifespan=lifespan, docs_url=None if PRODUCTION else "/api/docs", redoc_url=None,
              openapi_url=None if PRODUCTION else "/api/openapi.json")

for r in (auth.router, admin.router, llm.router, data.router, product.router, studio.router, chat.router, govern.router, public.router):
    app.include_router(r)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if not request.url.path.startswith(("/v1/widget", "/widget.js")):
        resp.headers.setdefault("X-Frame-Options", "DENY")
    if PRODUCTION:
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resp


@app.exception_handler(RequestValidationError)
async def _validation(request: Request, exc: RequestValidationError):
    msgs = [f"{'.'.join(str(x) for x in e['loc'][1:]) or 'body'}: {e['msg']}" for e in exc.errors()]
    return JSONResponse({"detail": "; ".join(msgs)}, status_code=422)


@app.api_route("/healthz", methods=["GET", "HEAD"])
def healthz():
    return {"ok": True, "env": ENV}


# ------------------------------------------------------------------ the web app (built React bundle)
DIST = ROOT / "frontend" / "dist"
if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
def spa(path: str):
    if path.startswith(("api/", "v1/")):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    f = (DIST / path).resolve()
    if path and f.is_file() and str(f).startswith(str(DIST.resolve())):
        return FileResponse(f)
    index = DIST / "index.html"
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-store"})
    return JSONResponse({"detail": "Frontend not built. Run: cd frontend && npm install && npm run build"}, status_code=503)
