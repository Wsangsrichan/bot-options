import json
import os
import sqlite3
from typing import Optional


class OptionsStore:
    def __init__(self, db_path: str = "./data/options.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY,
                ticker TEXT NOT NULL,
                underlying_price REAL,
                fetched_at TEXT,
                option_count INTEGER,
                options TEXT
            )
        """)

    def save_snapshot(self, ticker: str, underlying_price: float,
                      fetched_at: str, option_count: int,
                      options: list[dict]) -> int:
        cur = self.conn.execute(
            "INSERT INTO snapshots (ticker, underlying_price, fetched_at, option_count, options) "
            "VALUES (?, ?, ?, ?, ?)",
            (ticker, underlying_price, fetched_at, option_count,
             json.dumps(options)),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_snapshots(self, ticker: Optional[str] = None,
                      limit: int = 100) -> list[dict]:
        if ticker:
            rows = self.conn.execute(
                "SELECT * FROM snapshots WHERE ticker = ? ORDER BY id DESC LIMIT ?",
                (ticker, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM snapshots ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["options"] = json.loads(d["options"])
            result.append(d)
        return result

    def get_latest(self, ticker: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM snapshots WHERE ticker = ? ORDER BY id DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["options"] = json.loads(d["options"])
        return d

    def close(self):
        self.conn.close()
