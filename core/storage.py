"""attendance 테이블 SQLite 접근."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass


@dataclass
class Attendance:
    work_date: str
    clock_in: str
    clock_out: str | None
    work_seconds: int | None


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS attendance (
    work_date    TEXT PRIMARY KEY,
    clock_in     TEXT NOT NULL,
    clock_out    TEXT,
    work_seconds INTEGER
)
"""


class Storage:
    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_SQL)
        self._conn.commit()

    def get(self, work_date: str) -> Attendance | None:
        cur = self._conn.execute(
            "SELECT work_date, clock_in, clock_out, work_seconds "
            "FROM attendance WHERE work_date = ?",
            (work_date,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return Attendance(
            row["work_date"], row["clock_in"], row["clock_out"], row["work_seconds"]
        )

    def upsert(self, rec: Attendance) -> None:
        self._conn.execute(
            "INSERT INTO attendance (work_date, clock_in, clock_out, work_seconds) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(work_date) DO UPDATE SET "
            "clock_in=excluded.clock_in, clock_out=excluded.clock_out, "
            "work_seconds=excluded.work_seconds",
            (rec.work_date, rec.clock_in, rec.clock_out, rec.work_seconds),
        )
        self._conn.commit()

    def list_month(self, year: int, month: int) -> list[Attendance]:
        prefix = f"{year:04d}-{month:02d}-"
        cur = self._conn.execute(
            "SELECT work_date, clock_in, clock_out, work_seconds "
            "FROM attendance WHERE work_date LIKE ? ORDER BY work_date",
            (prefix + "%",),
        )
        return [
            Attendance(r["work_date"], r["clock_in"], r["clock_out"], r["work_seconds"])
            for r in cur.fetchall()
        ]

    def close(self) -> None:
        self._conn.close()
