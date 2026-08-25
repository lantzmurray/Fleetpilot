"""Append-only audit journal. Every decision is replayable."""
import json
import os
import sqlite3
import time


class Journal:
    def __init__(self, path: str = "journal/audit.db"):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            " id INTEGER PRIMARY KEY, ts REAL, kind TEXT, payload TEXT)")
        self.conn.commit()

    def log(self, kind: str, payload: dict) -> int:
        cur = self.conn.execute(
            "INSERT INTO events (ts, kind, payload) VALUES (?, ?, ?)",
            (time.time(), kind, json.dumps(payload, default=str)))
        self.conn.commit()
        return cur.lastrowid

    def replay(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, ts, kind, payload FROM events ORDER BY id").fetchall()
        return [{"id": r[0], "ts": r[1], "kind": r[2],
                 "payload": json.loads(r[3])} for r in rows]
