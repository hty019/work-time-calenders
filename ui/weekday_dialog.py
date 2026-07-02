"""요일 단위 계획 근무시간 일괄 수정 다이얼로그."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QMessageBox, QFormLayout, QLabel,
)

from ui.day_dialog import MAX_PLAN_MINUTES


def open_weekday_plan_dialog(
    parent,
    weekday_name: str,
    date_count: int,
    default_minutes: int,
    on_apply: Callable[[Optional[int]], None],
) -> None:
    """해당 요일 전체 날짜에 적용할 계획(분)을 입력받아 on_apply 로 전달."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"{weekday_name} 계획 일괄 수정")
    layout = QVBoxLayout(dlg)

    info = QLabel(f"이번 달 {weekday_name} {date_count}일에 일괄 적용됩니다.")
    layout.addWidget(info)

    form = QFormLayout()
    plan_edit = QLineEdit()
    plan_edit.setPlaceholderText(f"분 단위 (비우면 기본 {default_minutes}분으로 초기화)")
    form.addRow("계획(분)", plan_edit)
    layout.addLayout(form)

    buttons = QHBoxLayout()
    cancel = QPushButton("닫기")
    cancel.clicked.connect(dlg.reject)
    save = QPushButton("적용")
    buttons.addWidget(cancel)
    buttons.addWidget(save)
    layout.addLayout(buttons)

    def handle_save() -> None:
        text = plan_edit.text().strip()
        if text == "":
            on_apply(None)  # 오버라이드 해제 → 기본값 복귀
        else:
            if not text.isdigit():
                QMessageBox.warning(dlg, "입력 오류", "계획은 0 이상 정수(분)여야 합니다.")
                return
            minutes = int(text)
            if minutes > MAX_PLAN_MINUTES:
                QMessageBox.warning(dlg, "입력 오류", "계획은 하루 24시간을 넘을 수 없습니다.")
                return
            on_apply(minutes)
        dlg.accept()

    save.clicked.connect(handle_save)
    dlg.exec()
