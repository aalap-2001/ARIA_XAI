"""Data connections: Postgres, MySQL, SQL Server, uploaded files (CSV / Excel / SQLite) and REST APIs.
Everything is read-only. Credentials are encrypted at rest. Queries pass the SQL guard first."""
import csv
import io
import ipaddress
import json
import os
import re
import socket
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

from .config import DATA_DIR, PRODUCTION
from .models import DataConnection
from .security import decrypt_json
from .sql_guard import guard

BLOCK_PRIVATE = os.environ.get("ARIAX_BLOCK_PRIVATE_NETWORKS", "1" if PRODUCTION else "0") == "1"

KINDS = [
    {"id": "postgres", "name": "PostgreSQL", "fields": [
        {"name": "host", "label": "Host", "required": True}, {"name": "port", "label": "Port", "default": "5432"},
        {"name": "database", "label": "Database", "required": True}, {"name": "username", "label": "Username", "required": True},
        {"name": "password", "label": "Password", "secret": True}, {"name": "sslmode", "label": "SSL mode", "default": "prefer"}]},
    {"id": "mysql", "name": "MySQL / MariaDB", "fields": [
        {"name": "host", "label": "Host", "required": True}, {"name": "port", "label": "Port", "default": "3306"},
        {"name": "database", "label": "Database", "required": True}, {"name": "username", "label": "Username", "required": True},
        {"name": "password", "label": "Password", "secret": True}]},
    {"id": "mssql", "name": "SQL Server", "fields": [
        {"name": "host", "label": "Host", "required": True}, {"name": "port", "label": "Port", "default": "1433"},
        {"name": "database", "label": "Database", "required": True}, {"name": "username", "label": "Username", "required": True},
        {"name": "password", "label": "Password", "secret": True}]},
    {"id": "rest", "name": "REST API", "fields": [
        {"name": "base_url", "label": "Base URL", "required": True, "placeholder": "https://api.example.com"},
        {"name": "openapi_url", "label": "OpenAPI / Swagger URL (optional)", "placeholder": "https://api.example.com/openapi.json"},
        {"name": "auth_header", "label": "Auth header name", "default": "Authorization"},
        {"name": "auth_value", "label": "Auth header value", "secret": True, "placeholder": "Bearer …"}]},
    {"id": "upload", "name": "Upload a file", "upload": True, "accept": ".csv,.xlsx,.db,.sqlite,.sqlite3",
     "fields": []},
]
KIND_IDS = {k["id"] for k in KINDS}


class DataError(Exception):
    pass


def _check_host(host: str):
    if not BLOCK_PRIVATE:
        return
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise DataError(f"'{host}' resolves to a private address; private networks are blocked on this deployment")
    except socket.gaierror as ex:
        raise DataError(f"Cannot resolve host '{host}'") from ex


def upload_path(conn: DataConnection) -> Path:
    p = DATA_DIR / "orgs" / conn.org_id / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{conn.id}.sqlite"


def sql_engine(conn: DataConnection, write: bool = False):
    cfg, sec = conn.config, decrypt_json(conn.secret_enc)
    if conn.kind == "upload":
        path = upload_path(conn)
        mode = "rw" if write else "ro"
        return create_engine("sqlite://", creator=lambda: sqlite3.connect(f"file:{path.as_posix()}?mode={mode}", uri=True, check_same_thread=False))
    _check_host(cfg["host"])
    driver = {"postgres": "postgresql+psycopg", "mysql": "mysql+pymysql", "mssql": "mssql+pymssql"}[conn.kind]
    if conn.kind == "mssql":
        try:
            import pymssql  # noqa: F401
        except ImportError as ex:
            raise DataError("SQL Server support needs the 'pymssql' package installed on the server") from ex
    query = {"sslmode": cfg.get("sslmode", "prefer")} if conn.kind == "postgres" else {}
    url = URL.create(driver, username=cfg.get("username"), password=sec.get("password"), host=cfg["host"],
                     port=int(cfg.get("port") or 0) or None, database=cfg.get("database"), query=query)
    args = {"connect_timeout": 10} if conn.kind in ("postgres", "mysql") else {"login_timeout": 10}
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2, connect_args=args)


def _plain(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return f"<{len(bytes(v))} bytes>"
    return v


def introspect(conn: DataConnection) -> dict:
    if conn.kind == "rest":
        return introspect_rest(conn)
    eng = sql_engine(conn)
    try:
        insp = inspect(eng)
        tables = []
        names = insp.get_table_names()[:80]
        with eng.connect() as c:
            for t in names:
                cols = [{"name": col["name"], "type": str(col["type"])} for col in insp.get_columns(t)]
                pk = insp.get_pk_constraint(t).get("constrained_columns") or []
                fks = [{"columns": f["constrained_columns"], "references": f["referred_table"]} for f in insp.get_foreign_keys(t)]
                q = eng.dialect.identifier_preparer.quote(t)
                try:
                    rows = c.execute(text(f"SELECT COUNT(*) FROM {q}")).scalar()
                except Exception:  # noqa: BLE001
                    rows = None
                try:
                    lim = f"SELECT TOP 3 * FROM {q}" if conn.kind == "mssql" else f"SELECT * FROM {q} LIMIT 3"
                    res = c.execute(text(lim))
                    sample = [{k: _plain(v) for k, v in zip(res.keys(), r)} for r in res.fetchall()]
                except Exception:  # noqa: BLE001
                    sample = []
                tables.append({"name": t, "columns": cols, "primary_key": pk, "foreign_keys": fks, "rows": rows, "sample": sample})
        return {"kind": conn.kind, "tables": tables}
    except DataError:
        raise
    except Exception as ex:  # noqa: BLE001
        raise DataError(f"{type(ex).__name__}: {str(ex).splitlines()[0][:300]}") from ex
    finally:
        eng.dispose()


def run_query(conn: DataConnection, sql: str, allowed_tables: list[str], limit=200) -> dict:
    known = [t["name"] for t in (conn.schema_snapshot or {}).get("tables", [])]
    safe, used = guard(sql, conn.kind, known, allowed_tables, limit)
    eng = sql_engine(conn)
    try:
        with eng.connect() as c:
            if conn.kind == "postgres":
                c.execute(text("SET TRANSACTION READ ONLY"))
                c.execute(text("SET LOCAL statement_timeout = 15000"))
            elif conn.kind == "mysql":
                c.execute(text("SET SESSION TRANSACTION READ ONLY"))
                c.execute(text("SET SESSION MAX_EXECUTION_TIME = 15000"))
            res = c.execute(text(safe))
            cols = list(res.keys())
            rows = [[_plain(v) for v in r] for r in res.fetchmany(limit)]
            c.rollback()
        return {"sql": safe, "tables": used, "columns": cols, "rows": rows, "row_count": len(rows), "truncated": len(rows) >= limit}
    except Exception as ex:  # noqa: BLE001
        raise DataError(f"Query failed: {str(ex).splitlines()[0][:300]}") from ex
    finally:
        eng.dispose()


def write_row(conn: DataConnection, executor: dict, values: dict) -> dict:
    """Carry out ONE declared write for an approved action: an INSERT, or an UPDATE of exactly one row by key.
    Only the action's declared columns are written; anything else in the payload is ignored."""
    from sqlalchemy import MetaData, Table
    if conn.kind == "rest":
        raise DataError("REST connections cannot be written to directly; use a webhook action")
    if not (conn.config or {}).get("allow_writes"):
        raise DataError(f"Writes are not enabled on '{conn.name}'. An admin must enable them in Understand my product → data.")
    table, op = executor.get("table"), executor.get("operation")
    known = {t["name"]: {c["name"] for c in t.get("columns", [])} for t in (conn.schema_snapshot or {}).get("tables", [])}
    if table not in known:
        raise DataError(f"Table '{table}' is not part of this connection")
    allowed = [c for c in executor.get("columns") or [] if c in known[table]]
    data = {c: values[c] for c in allowed if c in values}
    eng = sql_engine(conn, write=True)
    try:
        t = Table(table, MetaData(), autoload_with=eng)
        with eng.begin() as c:  # one transaction: any failure rolls everything back
            if op == "insert":
                if not data:
                    raise DataError("None of the action's writable columns were provided")
                c.execute(t.insert().values(**data))
                return {"operation": "insert", "table": table, "rows": 1, "values": data}
            key = executor.get("key_column")
            if key not in known[table] or values.get(key) in (None, ""):
                raise DataError(f"The key '{key}' is needed to update a row")
            data.pop(key, None)
            if not data:
                raise DataError("None of the action's writable columns were provided")
            n = c.execute(t.update().where(t.c[key] == values[key]).values(**data)).rowcount
            if n != 1:
                raise DataError(f"Expected exactly one row where {key} = {values[key]}, found {n}; nothing was changed")
            return {"operation": "update", "table": table, "rows": 1, "key": {key: values[key]}, "values": data}
    except DataError:
        raise
    except Exception as ex:  # noqa: BLE001
        raise DataError(f"Write failed: {str(ex).splitlines()[0][:300]}") from ex
    finally:
        eng.dispose()


# ---------------------------------------------------------------------------- uploads
def _clean(name: str) -> str:
    n = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_").lower() or "data"
    return ("t_" + n) if n[0].isdigit() else n


def _infer(values):
    def ok(fn):
        try:
            for v in values:
                if v not in ("", None):
                    fn(v)
            return True
        except (TypeError, ValueError):
            return False
    if ok(int):
        return "INTEGER", lambda v: None if v in ("", None) else int(v)
    if ok(float):
        return "REAL", lambda v: None if v in ("", None) else float(v)
    return "TEXT", lambda v: None if v is None else str(v)


def _write_table(db: sqlite3.Connection, table: str, header: list, rows: list):
    header = [_clean(h or f"col{i + 1}") for i, h in enumerate(header)]
    seen = {}
    for i, h in enumerate(header):  # de-duplicate column names
        if h in seen:
            seen[h] += 1
            header[i] = f"{h}_{seen[h]}"
        else:
            seen[h] = 0
    cols = list(zip(*rows)) if rows else [[] for _ in header]
    types = [_infer(list(c)) for c in cols] if rows else [("TEXT", str)] * len(header)
    db.execute(f'DROP TABLE IF EXISTS "{table}"')
    db.execute(f'CREATE TABLE "{table}" (' + ", ".join(f'"{h}" {t[0]}' for h, t in zip(header, types)) + ")")
    db.executemany(f'INSERT INTO "{table}" VALUES (' + ",".join("?" * len(header)) + ")",
                   [[types[i][1](r[i] if i < len(r) else None) for i in range(len(header))] for r in rows])


def build_upload(conn: DataConnection, filename: str, data: bytes):
    path = upload_path(conn)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("db", "sqlite", "sqlite3"):
        if not data.startswith(b"SQLite format 3\x00"):
            raise DataError("This file is not a SQLite database")
        path.write_bytes(data)
        return
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    try:
        if ext == "csv":
            rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace"))))
            if not rows:
                raise DataError("The CSV file is empty")
            _write_table(db, _clean(filename.rsplit(".", 1)[0]), rows[0], rows[1:200001])
        elif ext == "xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            for ws in wb.worksheets:
                rows = [list(r) for r in ws.iter_rows(values_only=True)]
                rows = [r for r in rows if any(v is not None for v in r)]
                if rows:
                    _write_table(db, _clean(ws.title), [str(h or "") for h in rows[0]],
                                 [["" if v is None else v for v in r] for r in rows[1:200001]])
        else:
            raise DataError("Upload a .csv, .xlsx or SQLite (.db/.sqlite) file")
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------- REST
def _rest_client(conn: DataConnection) -> httpx.Client:
    cfg, sec = conn.config, decrypt_json(conn.secret_enc)
    _check_host(urlparse(cfg["base_url"]).hostname or "")
    headers = {"Accept": "application/json", "User-Agent": "AriaX/1.0"}
    if sec.get("auth_value"):
        headers[cfg.get("auth_header") or "Authorization"] = sec["auth_value"]
    return httpx.Client(timeout=15, headers=headers, follow_redirects=False)


def introspect_rest(conn: DataConnection) -> dict:
    cfg = conn.config
    endpoints = []
    with _rest_client(conn) as c:
        if cfg.get("openapi_url"):
            try:
                r = c.get(cfg["openapi_url"])
                r.raise_for_status()
                spec = r.json()
                for path, ops in (spec.get("paths") or {}).items():
                    if isinstance(ops, dict) and "get" in ops:
                        op = ops["get"]
                        endpoints.append({"path": path, "summary": (op.get("summary") or op.get("description") or "")[:200],
                                          "params": [p.get("name") for p in op.get("parameters", []) if isinstance(p, dict)]})
            except Exception as ex:  # noqa: BLE001
                raise DataError(f"Could not read the OpenAPI document: {type(ex).__name__}: {str(ex)[:200]}") from ex
        else:
            try:
                r = c.get(cfg["base_url"])
                endpoints.append({"path": "/", "summary": f"HTTP {r.status_code}", "params": []})
            except Exception as ex:  # noqa: BLE001
                raise DataError(f"Could not reach the API: {type(ex).__name__}") from ex
    return {"kind": "rest", "endpoints": endpoints[:100], "tables": []}


def call_api(conn: DataConnection, path: str, params: dict | None) -> dict:
    allowed = [e["path"] for e in (conn.schema_snapshot or {}).get("endpoints", [])]
    tmpl = re.compile("^" + "|".join("(" + re.sub(r"\\\{[^}]+\\\}", "[^/]+", re.escape(p)) + ")" for p in allowed) + "$") if allowed else None
    if not path.startswith("/") or ".." in path or (tmpl and not tmpl.match(path.split("?")[0])):
        raise DataError(f"Path '{path}' is not one of this API's documented GET endpoints")
    with _rest_client(conn) as c:
        r = c.get(urljoin(conn.config["base_url"].rstrip("/") + "/", path.lstrip("/")), params=params or {})
        try:
            body = r.json()
        except json.JSONDecodeError:
            body = r.text[:4000]
        s = json.dumps(body, default=str)
        return {"status": r.status_code, "body": json.loads(s[:20000]) if len(s) <= 20000 else s[:20000] + "…(truncated)"}
