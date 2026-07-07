"""복수 날짜(요일·다중 선택) 계획 근무시간·인정 범위 일괄 수정 다이얼로그."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QMessageBox, QFormLayout, QLabel,
)

from core.recognition import RecognitionRange
from ui import theme
from ui.day_dialog import MAX_PLAN_MINUTES, parse_recognition_inputs


def open_bulk_plan_dialog(
    parent,
    title: str,
    info_text: str,
    default_minutes: int,
    on_apply: Callable[[Optional[int], Optional[RecognitionRange]], None],
    validate: Callable[[Optional[int], Optional[RecognitionRange]], Optional[str]],
) -> bool:
    """대상 날짜들에 적용할 계획(분)·인정 범위를 입력받아 on_apply 로 전달.

    validate 가 오류 메시지를 반환하면 경고를 띄우고 저장을 막는다.
    적용했으면 True, 취소했으면 False 를 반환한다.
    """
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(theme.BULK_PLAN_DIALOG_MIN_WIDTH)
    layout = QVBoxLayout(dlg)

    info = QLabel(info_text)  # HTML 포함 가능 (보조 문구 색상 등)
    layout.addWidget(info)

    form = QFormLayout()
    plan_edit = QLineEdit()
    plan_edit.setPlaceholderText(f"분 단위 (비우면 기본 {default_minutes}분으로 초기화)")
    recog_start_edit = QLineEdit()
    recog_start_edit.setPlaceholderText("HH:MM (비우면 미설정)")
    recog_end_edit = QLineEdit()
    recog_end_edit.setPlaceholderText("HH:MM (비우면 미설정)")
    form.addRow("실 계획(분)", plan_edit)
    form.addRow("(가)계획 시작", recog_start_edit)
    form.addRow("(가)계획 종료", recog_end_edit)
    layout.addLayout(form)

    buttons = QHBoxLayout()
    cancel = QPushButton("닫기")
    cancel.clicked.connect(dlg.reject)
    save = QPushButton("적용")
    buttons.addWidget(cancel)
    buttons.addWidget(save)
    layout.addLayout(buttons)

    def handle_save() -> None:
        # 1) 계획 파싱
        text = plan_edit.text().strip()
        minutes: Optional[int] = None
        if text != "":
            if not text.isdigit():
                QMessageBox.warning(dlg, "입력 오류", "계획은 0 이상 정수(분)여야 합니다.")
                return
            minutes = int(text)
            if minutes > MAX_PLAN_MINUTES:
                QMessageBox.warning(dlg, "입력 오류", "계획은 하루 24시간을 넘을 수 없습니다.")
                return

        # 2) 인정 범위 파싱
        try:
            rng = parse_recognition_inputs(
                recog_start_edit.text(), recog_end_edit.text()
            )
        except ValueError as exc:
            QMessageBox.warning(dlg, "입력 오류", str(exc))
            return

        # 3) 날짜별 검증 (계획 대비 범위 폭)
        err = validate(minutes, rng)
        if err is not None:
            QMessageBox.warning(dlg, "입력 오류", err)
            return

        on_apply(minutes, rng)
        dlg.accept()

    save.clicked.connect(handle_save)
    return dlg.exec() == QDialog.Accepted
