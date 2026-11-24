"""Thin thread-safe SQLite wrapper for platform state (bundles, audit, runs).
The Knowledge Fabric's governed store is a separate database reached only via connectors."""
import json
import sqlite3
import threading


class Store:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")

    def executescript(self, sql: str):
        with self.lock:
            self.conn.executescript(sql)

    def execute(self, sql: str, params=()):
        with self.lock:
            return self.conn.execute(sql, params)

    def all(self, sql: str, params=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params=()) -> dict | None:
        with self.lock:
            r = self.conn.execute(sql, params).fetchone()
            return dict(r) if r else None


def dumps(v) -> str:
    return json.dumps(v, default=str)


def loads(s, default=None):
    if s in (None, ""):
        return default
    return json.loads(s)
