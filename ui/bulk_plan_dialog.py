"""복수 날짜(요일·다중 선택) 계획 근무시간·인정 범위 일괄 수정 다이얼로그."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QMessageBox, QFormLayout, QLabel, QComboBox, QStyleFactory,
)

from core.recognition import RecognitionRange, hhmm_to_minutes
from core.vacation import FULL_DAY_MINUTES, Vacation, build_vacation
from ui import theme
from ui.day_dialog import (
    MAX_PLAN_MINUTES,
    VACATION_CHOICES,
    parse_recognition_inputs,
)

# 일괄 적용에서 기존 휴가를 실수로 지우지 않기 위한 기본 선택지
_VACATION_KEEP_LABEL = "변경 없음"


def open_bulk_plan_dialog(
    parent,
    title: str,
    info_text: str,
    default_minutes: int,
    on_apply: Callable[[Optional[int], Optional[RecognitionRange]], None],
    validate: Callable[[Optional[int], Optional[RecognitionRange]], Optional[str]],
    on_apply_vacation: Optional[Callable[[Optional[Vacation]], None]] = None,
) -> bool:
    """대상 날짜들에 적용할 계획(분)·인정 범위를 입력받아 on_apply 로 전달.

    validate 가 오류 메시지를 반환하면 경고를 띄우고 저장을 막는다.
    on_apply_vacation 이 주어지면 휴가 입력 행이 추가된다 — '변경 없음'이면
    호출하지 않고, '없음'은 해제(None), 그 외는 Vacation 을 전달한다.
    적용했으면 True, 취소했으면 False 를 반환한다.
    """
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    layout = QVBoxLayout(dlg)

    info = QLabel(info_text)  # HTML 포함 가능 (보조 문구 색상 등)
    layout.addWidget(info)

    form = QFormLayout()
    # macOS 기본 정책은 입력란을 sizeHint 로 고정 — 폭을 따라 늘어나게 함
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    plan_edit = QLineEdit()
    plan_edit.setPlaceholderText(f"기본값:{default_minutes}")
    recog_start_edit = QLineEdit()
    recog_start_edit.setPlaceholderText("HH:MM (비우면 미설정)")
    recog_end_edit = QLineEdit()
    recog_end_edit.setPlaceholderText("HH:MM (비우면 미설정)")
    form.addRow("실 계획(분)", plan_edit)
    form.addRow("(가)계획 시작", recog_start_edit)
    form.addRow("(가)계획 종료", recog_end_edit)

    if on_apply_vacation is not None:
        vacation_combo = QComboBox()
        vacation_combo.setStyle(QStyleFactory.create("Fusion"))
        vacation_combo.addItem(_VACATION_KEEP_LABEL)
        for label, _minutes in VACATION_CHOICES:
            vacation_combo.addItem(label)
        vacation_start_edit = QLineEdit()
        vacation_start_edit.setPlaceholderText("HH:MM (시간제 휴가만)")
        vacation_start_label = QLabel("휴가 시작")
        form.addRow("휴가", vacation_combo)
        form.addRow(vacation_start_label, vacation_start_edit)

        def _hourly_selected() -> bool:
            """시간제 휴가(2h/4h/6h) 선택 여부. 변경 없음·없음·1day 제외."""
            idx = vacation_combo.currentIndex()
            if idx == 0:
                return False
            minutes = VACATION_CHOICES[idx - 1][1]
            return minutes is not None and minutes < FULL_DAY_MINUTES

        def _update_vacation_start_visibility() -> None:
            visible = _hourly_selected()
            vacation_start_label.setVisible(visible)
            vacation_start_edit.setVisible(visible)

        vacation_combo.currentIndexChanged.connect(
            lambda _index: _update_vacation_start_visibility()
        )
        _update_vacation_start_visibility()

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

        # 4) 휴가 파싱 ('변경 없음'이면 기존 휴가를 건드리지 않음)
        vacation_changed = False
        new_vacation: Optional[Vacation] = None
        if on_apply_vacation is not None and vacation_combo.currentIndex() > 0:
            vacation_changed = True
            vac_minutes = VACATION_CHOICES[vacation_combo.currentIndex() - 1][1]
            if vac_minutes is not None:
                try:
                    # 시작 시각은 시간제일 때만 사용 (숨겨진 입력 값은 무시)
                    start_min = None
                    if _hourly_selected():
                        start_text = vacation_start_edit.text().strip()
                        start_min = (
                            hhmm_to_minutes(start_text) if start_text else None
                        )
                    new_vacation = build_vacation(vac_minutes, start_min=start_min)
                except ValueError as exc:
                    QMessageBox.warning(dlg, "입력 오류", str(exc))
                    return

        on_apply(minutes, rng)
        if vacation_changed:
            on_apply_vacation(new_vacation)
        dlg.accept()

    save.clicked.connect(handle_save)
    # 자연 크기 + 소폭 여유 (입력란은 성장 정책으로 함께 늘어남)
    dlg.setMinimumWidth(
        dlg.sizeHint().width() + theme.BULK_PLAN_DIALOG_EXTRA_W_PX
    )
    return dlg.exec() == QDialog.Accepted
