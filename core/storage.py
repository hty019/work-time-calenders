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

_CREATE_PLAN_SQL = """
CREATE TABLE IF NOT EXISTS plan (
    work_date       TEXT PRIMARY KEY,
    planned_minutes INTEGER NOT NULL
)
"""

_CREATE_RECOGNITION_SQL = """
CREATE TABLE IF NOT EXISTS recognition (
    work_date TEXT PRIMARY KEY,
    start_min INTEGER NOT NULL,
    end_min   INTEGER NOT NULL
)
"""

_CREATE_VACATION_SQL = """
CREATE TABLE IF NOT EXISTS vacation (
    work_date TEXT PRIMARY KEY,
    minutes   INTEGER NOT NULL,
    start_min INTEGER,
    end_min   INTEGER
)
"""


class Storage:
    def __init__(self, db_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_SQL)
        self._conn.execute(_CREATE_PLAN_SQL)
        self._conn.execute(_CREATE_RECOGNITION_SQL)
        self._conn.execute(_CREATE_VACATION_SQL)
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

    def get_plan(self, work_date: str) -> int | None:
        cur = self._conn.execute(
            "SELECT planned_minutes FROM plan WHERE work_date = ?",
            (work_date,),
        )
        row = cur.fetchone()
        return int(row["planned_minutes"]) if row is not None else None

    def set_plan(self, work_date: str, planned_minutes: int) -> None:
        self._conn.execute(
            "INSERT INTO plan (work_date, planned_minutes) VALUES (?, ?) "
            "ON CONFLICT(work_date) DO UPDATE SET "
            "planned_minutes=excluded.planned_minutes",
            (work_date, planned_minutes),
        )
        self._conn.commit()

    def clear_plan(self, work_date: str) -> None:
        self._conn.execute("DELETE FROM plan WHERE work_date = ?", (work_date,))
        self._conn.commit()

    def list_plan_month(self, year: int, month: int) -> dict[str, int]:
        prefix = f"{year:04d}-{month:02d}-"
        cur = self._conn.execute(
            "SELECT work_date, planned_minutes FROM plan "
            "WHERE work_date LIKE ? ORDER BY work_date",
            (prefix + "%",),
        )
        return {r["work_date"]: int(r["planned_minutes"]) for r in cur.fetchall()}

    def get_recognition(self, work_date: str) -> tuple[int, int] | None:
        """해당 날짜의 인정 범위 (시작분, 종료분). 없으면 None."""
        cur = self._conn.execute(
            "SELECT start_min, end_min FROM recognition WHERE work_date = ?",
            (work_date,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return int(row["start_min"]), int(row["end_min"])

    def set_recognition(
        self, work_date: str, start_min: int, end_min: int
    ) -> None:
        self._conn.execute(
            "INSERT INTO recognition (work_date, start_min, end_min) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(work_date) DO UPDATE SET "
            "start_min=excluded.start_min, end_min=excluded.end_min",
            (work_date, start_min, end_min),
        )
        self._conn.commit()

    def clear_recognition(self, work_date: str) -> None:
        self._conn.execute(
            "DELETE FROM recognition WHERE work_date = ?", (work_date,)
        )
        self._conn.commit()

    def list_recognition_month(
        self, year: int, month: int
    ) -> dict[str, tuple[int, int]]:
        prefix = f"{year:04d}-{month:02d}-"
        cur = self._conn.execute(
            "SELECT work_date, start_min, end_min FROM recognition "
            "WHERE work_date LIKE ? ORDER BY work_date",
            (prefix + "%",),
        )
        return {
            r["work_date"]: (int(r["start_min"]), int(r["end_min"]))
            for r in cur.fetchall()
        }

    def get_vacation(self, work_date: str) -> tuple[int, int | None, int | None] | None:
        """해당 날짜의 휴가 (분, 시작분, 종료분). 없으면 None."""
        cur = self._conn.execute(
            "SELECT minutes, start_min, end_min FROM vacation WHERE work_date = ?",
            (work_date,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return (
            int(row["minutes"]),
            int(row["start_min"]) if row["start_min"] is not None else None,
            int(row["end_min"]) if row["end_min"] is not None else None,
        )

    def set_vacation(
        self,
        work_date: str,
        minutes: int,
        start_min: int | None,
        end_min: int | None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO vacation (work_date, minutes, start_min, end_min) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(work_date) DO UPDATE SET "
            "minutes=excluded.minutes, start_min=excluded.start_min, "
            "end_min=excluded.end_min",
            (work_date, minutes, start_min, end_min),
        )
        self._conn.commit()

    def clear_vacation(self, work_date: str) -> None:
        self._conn.execute("DELETE FROM vacation WHERE work_date = ?", (work_date,))
        self._conn.commit()

    def list_vacation_month(
        self, year: int, month: int
    ) -> dict[str, tuple[int, int | None, int | None]]:
        prefix = f"{year:04d}-{month:02d}-"
        cur = self._conn.execute(
            "SELECT work_date, minutes, start_min, end_min FROM vacation "
            "WHERE work_date LIKE ? ORDER BY work_date",
            (prefix + "%",),
        )
        return {
            r["work_date"]: (
                int(r["minutes"]),
                int(r["start_min"]) if r["start_min"] is not None else None,
                int(r["end_min"]) if r["end_min"] is not None else None,
            )
            for r in cur.fetchall()
        }

    def close(self) -> None:
        self._conn.close()
