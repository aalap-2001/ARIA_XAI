"""Build ONE deployable zip of Aria XAI for a devops engineer: Docker, preloaded demo data, one guide, one command.

    python scripts/make_deploy.py [output.zip]

The AI model keys and all sign-in sessions are removed from the packaged database. The master key goes into the packaged
.env (it unlocks the demo documents), so keep the zip private.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC.parent / "aria-xai-deploy.zip"
TOP = "aria-xai"
SKIP_DIRS = {"node_modules", "__pycache__", ".pytest_cache", ".venv", "venv", ".git", "dist", "data"}
SKIP_FILES = {".env", ".env.example", "docker-compose.yml", "Dockerfile", "DUMP-README.md"}
DBS = ["ariax.db", "platform.db", "fabric.db"]

DOCKERFILE = """# Aria XAI: builds the web app, then runs the server. Demo data in seed-data/ is copied into the data volume on first start.
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ARIAX_ENV=production ARIAX_DATA_DIR=/data
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY ariax/ ariax/
COPY backend/app/ backend/app/
COPY --from=web /web/dist frontend/dist
RUN useradd --create-home --uid 10001 ariax && mkdir -p /data && chown ariax /data
COPY --chown=ariax seed-data/ /data/
USER ariax
VOLUME /data
EXPOSE 8700
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8700/healthz')"
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8700", "--proxy-headers", "--forwarded-allow-ips", "*"]
"""

COMPOSE = """# Aria XAI. Start with:  docker compose up -d --build
services:
  app:
    build: .
    env_file: .env
    ports: ["8700:8700"]
    volumes: [ariax-data:/data]
    restart: unless-stopped

volumes:
  ariax-data:
"""

ENV = """# Aria XAI settings. Only ARIAX_BASE_URL needs changing.

# 1) The public address people will open in the browser (used in invite links and the chat widget).
ARIAX_BASE_URL=http://localhost:8700

# 2) Leave as 1 when the site is served over HTTPS (normal). Set to 0 ONLY for a quick test over plain http,
#    otherwise sign-in will not work over http.
ARIAX_COOKIE_SECURE=1

# 3) The AI model every business runs on. Set on the server only; there is no screen for it in the app.
ARIAX_LLM_API_KEY=
ARIAX_LLM_PROVIDER=anthropic
ARIAX_LLM_MODEL=claude-opus-5-5

# Do not change. Unlocks the encrypted demo documents and settings in the packaged data.
ARIAX_MASTER_KEY={key}
"""

DOCKERIGNORE = "**/node_modules\n**/__pycache__\n**/.pytest_cache\nfrontend/dist\n"

GUIDE = """# Deploy Aria XAI

This is the only guide you need. Everything (code, demo data, settings) is in this folder.

## What you need on the server

- Docker with Docker Compose (Docker Desktop, or Docker Engine with the compose plugin)
- Internet access during the build (it downloads Node and Python packages)
- HTTPS in front of port 8700 (your usual reverse proxy or load balancer)

## Steps

1. Unzip and go into the folder:

   ```
   unzip aria-xai-deploy.zip
   cd aria-xai
   ```

2. Open `.env` and set two values:
   - `ARIAX_BASE_URL`: the public address, for example `https://aria.yourcompany.com`
   - `ARIAX_LLM_API_KEY`: the AI model key the owner gives you (Anthropic by default)
   Nothing else in `.env` needs changing.

3. Start it:

   ```
   docker compose up -d --build
   ```

   The first build takes a few minutes. The app listens on port 8700.

4. Point your HTTPS proxy at `http://<server>:8700`.

5. Check it is healthy: `curl http://localhost:8700/healthz` returns `{"ok": true, ...}`.

Done. Open the public address, click Log in and use the logins the owner gave you.

## Everyday commands

| Task | Command |
|---|---|
| See logs | `docker compose logs -f app` |
| Restart | `docker compose restart app` |
| Stop | `docker compose down` (data is kept) |
| Update to a new zip | unzip over this folder, then `docker compose up -d --build` (data is kept) |
| Back up data | `docker run --rm -v aria-xai_ariax-data:/data -v "$PWD":/backup alpine tar czf /backup/ariax-data.tgz -C /data .` |

## Good to know

- All data (database, uploaded documents) lives in the Docker volume `ariax-data`. Do not run `docker compose down -v`, that deletes it.
- Demo data is copied into the volume only on the very first start. Later rebuilds never overwrite it.
- The AI model is configured only here, in `.env`. There is no AI models screen in the app. To change the key or model, edit `.env` and run `docker compose up -d`.
- Keep `.env` private: `ARIAX_MASTER_KEY` unlocks the stored data. If it is lost or changed, encrypted documents and settings cannot be read.

## If something goes wrong

| What you see | Fix |
|---|---|
| Sign-in does nothing over plain http | Expected: cookies are HTTPS-only. Use HTTPS, or for a quick test set `ARIAX_COOKIE_SECURE=0` in `.env` and run `docker compose up -d` |
| Agents answer "No AI model is configured" | Set `ARIAX_LLM_API_KEY` in `.env`, then `docker compose up -d` |
| Invite links show localhost | Set `ARIAX_BASE_URL` in `.env`, then `docker compose up -d` |
| Port 8700 already in use | In `docker-compose.yml` change `"8700:8700"` to e.g. `"8800:8700"` and proxy to 8800 |
| Build fails downloading packages | The server needs internet access during the build |
"""


def snapshot(src: Path, dst: Path):
    a, b = sqlite3.connect(src), sqlite3.connect(dst)
    with b:
        a.backup(b)
    a.close()
    b.close()


def scrub(db: Path):
    c = sqlite3.connect(db)
    tables = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
    if "llm_connectors" in tables:
        c.execute("delete from llm_connectors")  # the model is set on the server (.env), never stored in the app
    if "sessions" in tables:
        c.execute("delete from sessions")
    c.commit()
    c.execute("vacuum")
    c.close()


def main():
    stage = Path(tempfile.mkdtemp())
    root = stage / TOP
    for dirpath, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = Path(dirpath) / f
            rel = p.relative_to(SRC)
            if len(rel.parts) == 1 and f in SKIP_FILES:
                continue
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
    seed = root / "seed-data"
    seed.mkdir(parents=True)
    for db in DBS:
        if (SRC / "data" / db).exists():
            snapshot(SRC / "data" / db, seed / db)
            scrub(seed / db)
    shutil.copytree(SRC / "data" / "orgs", seed / "orgs")
    if (SRC / "data" / ".signing_key").exists():
        shutil.copy2(SRC / "data" / ".signing_key", seed / ".signing_key")
    key = (SRC / "data" / ".master_key").read_text().strip()
    (root / "Dockerfile").write_text(DOCKERFILE, newline="\n")
    (root / "docker-compose.yml").write_text(COMPOSE, newline="\n")
    (root / ".env").write_text(ENV.format(key=key), newline="\n")
    (root / ".dockerignore").write_text(DOCKERIGNORE, newline="\n")
    (root / "DEPLOY.md").write_text(GUIDE, newline="\n")
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(stage))
                n += 1
    shutil.rmtree(stage, ignore_errors=True)
    print(f"{OUT}  {n} files  {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
