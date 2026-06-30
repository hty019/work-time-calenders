"""출근/퇴근 시각 수정 다이얼로그."""
from __future__ import annotations

import re
from typing import Callable, Optional

_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_KST_OFFSET = "+09:00"


def build_iso(work_date: str, hhmm: str) -> str:
    """work_date(YYYY-MM-DD)와 HH:MM을 KST ISO8601 문자열로."""
    m = _HHMM_RE.match(hhmm.strip())
    if not m:
        raise ValueError(f"시각 형식은 HH:MM 이어야 합니다: {hhmm!r}")
    return f"{work_date}T{m.group(1)}:{m.group(2)}:00{_KST_OFFSET}"


def _hhmm_from_iso(iso: Optional[str]) -> str:
    if not iso:
        return ""
    # ...T09:05:00+09:00 → 09:05
    return iso[11:16]


def open_edit_dialog(
    parent,
    work_date: str,
    clock_in_iso: Optional[str],
    clock_out_iso: Optional[str],
    on_save: Callable[[str, str, Optional[str]], None],
) -> None:
    import tkinter as tk
    from tkinter import messagebox

    top = tk.Toplevel(parent)
    top.title(f"{work_date} 근무시간 수정")
    top.transient(parent)
    top.grab_set()

    tk.Label(top, text="출근 (HH:MM)").grid(row=0, column=0, padx=8, pady=6)
    in_var = tk.StringVar(value=_hhmm_from_iso(clock_in_iso))
    tk.Entry(top, textvariable=in_var, width=8).grid(row=0, column=1, padx=8)

    tk.Label(top, text="퇴근 (HH:MM, 비우면 미퇴근)").grid(row=1, column=0, padx=8, pady=6)
    out_var = tk.StringVar(value=_hhmm_from_iso(clock_out_iso))
    tk.Entry(top, textvariable=out_var, width=8).grid(row=1, column=1, padx=8)

    def handle_save() -> None:
        in_text = in_var.get().strip()
        if not in_text:
            messagebox.showwarning("입력 오류", "출근 시각을 입력하세요.", parent=top)
            return
        try:
            clock_in = build_iso(work_date, in_text)
            out_text = out_var.get().strip()
            clock_out = build_iso(work_date, out_text) if out_text else None
        except ValueError as exc:
            messagebox.showwarning("입력 오류", str(exc), parent=top)
            return
        try:
            on_save(work_date, clock_in, clock_out)
        except ValueError as exc:
            messagebox.showwarning("저장 실패", str(exc), parent=top)
            return
        top.destroy()

    tk.Button(top, text="저장", command=handle_save).grid(
        row=2, column=0, columnspan=2, pady=10
    )
