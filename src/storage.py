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
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS paper_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                option_type TEXT NOT NULL,
                strike REAL NOT NULL,
                expiration TEXT NOT NULL,
                entry_price REAL NOT NULL,
                entry_spot REAL NOT NULL,
                entry_delta REAL,
                entry_iv REAL,
                contracts INTEGER DEFAULT 1,
                entry_time TEXT NOT NULL,
                exit_price REAL,
                exit_time TEXT,
                pnl REAL DEFAULT 0,
                status TEXT DEFAULT 'open',
                trailing_high REAL DEFAULT 0
            )
        """)

        # Add trailing_high column if missing (migration for existing DBs)
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(paper_positions)").fetchall()]
        if "trailing_high" not in cols:
            self.conn.execute("ALTER TABLE paper_positions ADD COLUMN trailing_high REAL DEFAULT 0")
            self.conn.commit()

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

    def save_position(self, ticker, option_type, strike, expiration,
                       entry_price, entry_spot, entry_delta=None,
                       entry_iv=None, contracts=1) -> int:
        from datetime import datetime
        cur = self.conn.execute(
            "INSERT INTO paper_positions "
            "(ticker, option_type, strike, expiration, entry_price, entry_spot, "
            "entry_delta, entry_iv, contracts, entry_time) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ticker, option_type, strike, expiration, entry_price, entry_spot,
             entry_delta, entry_iv, contracts, datetime.now().isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_open_positions(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM paper_positions WHERE status = 'open' ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_trailing_high(self, position_id, price):
        self.conn.execute(
            "UPDATE paper_positions SET trailing_high=? WHERE id=?",
            (price, position_id),
        )
        self.conn.commit()

    def close_position(self, position_id, exit_price, exit_time, pnl):
        self.conn.execute(
            "UPDATE paper_positions SET exit_price=?, exit_time=?, pnl=?, status='closed' "
            "WHERE id=?",
            (exit_price, exit_time, pnl, position_id),
        )
        self.conn.commit()

    def get_position_history(self, limit=100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM paper_positions WHERE status = 'closed' "
            "ORDER BY exit_time DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_closed_positions(self, limit=200) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM paper_positions WHERE status = 'closed' "
            "ORDER BY exit_time ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_account_summary(self) -> dict:
        row = self.conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN status='open' THEN entry_price * contracts * 100 ELSE 0 END), 0) AS total_invested,
                COALESCE(SUM(CASE WHEN status='closed' THEN pnl ELSE 0 END), 0) AS total_pnl,
                COUNT(CASE WHEN status='open' THEN 1 END) AS open_count,
                COUNT(CASE WHEN status='closed' THEN 1 END) AS closed_count
            FROM paper_positions
        """).fetchone()
        return dict(row)

    def close(self):
        self.conn.close()
