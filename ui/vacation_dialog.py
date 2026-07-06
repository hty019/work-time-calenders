"""연간 휴가(연차) 현황 조회·총 연차 설정 다이얼로그."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QMessageBox, QFormLayout, QLabel, QTableWidget, QTableWidgetItem,
)

from core.recognition import minutes_to_hhmm
from core.vacation import (
    YearLeaveSummary,
    days_str_to_minutes,
    minutes_to_days_str,
)
from ui import theme
from ui.day_dialog import VACATION_CHOICES

_TYPE_LABELS = {m: label for label, m in VACATION_CHOICES if m is not None}
_TABLE_HEADERS = ["날짜", "유형", "구간", "소진(일)"]
_NO_RANGE = "-"


def _summary_text(summary: YearLeaveSummary) -> str:
    used = minutes_to_days_str(summary.used_minutes)
    if summary.total_minutes is None:
        return f"총 연차 미설정 · 소진 {used}일"
    total = minutes_to_days_str(summary.total_minutes)
    remaining = minutes_to_days_str(summary.remaining_minutes)
    return f"총 {total}일 · 소진 {used}일 · 잔여 {remaining}일"


def _fill_table(table: QTableWidget, summary: YearLeaveSummary) -> None:
    table.setRowCount(len(summary.entries))
    for row, (date, vac) in enumerate(summary.entries):
        rng = (
            f"{minutes_to_hhmm(vac.start_min)}~{minutes_to_hhmm(vac.end_min)}"
            if vac.start_min is not None
            else _NO_RANGE
        )
        cells = [
            date,
            _TYPE_LABELS.get(vac.minutes, f"{vac.minutes}분"),
            rng,
            minutes_to_days_str(vac.minutes),
        ]
        for col, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, col, item)


def open_vacation_dialog(
    parent,
    summary: YearLeaveSummary,
    on_save_total: Callable[[int], YearLeaveSummary],
) -> None:
    """연간 휴가 현황을 보여주고 총 연차(일) 수정 시 on_save_total 로 전달.

    on_save_total 은 저장 후의 갱신된 요약을 반환해 화면에 반영한다.
    """
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"{summary.year}년 휴가 관리")
    dlg.setMinimumSize(
        theme.VACATION_DIALOG_MIN_WIDTH, theme.VACATION_DIALOG_MIN_HEIGHT
    )
    layout = QVBoxLayout(dlg)

    summary_label = QLabel(_summary_text(summary))
    layout.addWidget(summary_label)

    table = QTableWidget(0, len(_TABLE_HEADERS))
    table.setHorizontalHeaderLabels(_TABLE_HEADERS)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    _fill_table(table, summary)
    layout.addWidget(table)

    form = QFormLayout()
    total_edit = QLineEdit(
        ""
        if summary.total_minutes is None
        else minutes_to_days_str(summary.total_minutes)
    )
    total_edit.setPlaceholderText("일 단위, 0.25 단위 허용 (예: 15 또는 15.5)")
    form.addRow("총 연차(일)", total_edit)
    layout.addLayout(form)

    buttons = QHBoxLayout()
    close_btn = QPushButton("닫기")
    close_btn.clicked.connect(dlg.reject)
    save_btn = QPushButton("총 연차 저장")
    buttons.addWidget(close_btn)
    buttons.addWidget(save_btn)
    layout.addLayout(buttons)

    def handle_save() -> None:
        try:
            total_minutes = days_str_to_minutes(total_edit.text())
        except ValueError as e:
            QMessageBox.warning(dlg, "입력 오류", str(e))
            return
        updated = on_save_total(total_minutes)
        summary_label.setText(_summary_text(updated))
        _fill_table(table, updated)

    save_btn.clicked.connect(handle_save)
    dlg.exec()
