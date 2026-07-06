"""날짜별 출퇴근 시각·계획 근무시간 편집 다이얼로그."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QMessageBox, QFormLayout, QComboBox, QLabel,
)

from core.recognition import (
    RecognitionRange,
    hhmm_to_minutes,
    minutes_to_hhmm,
    validate_range_against_plan,
)
from core.timefmt import build_iso
from core.vacation import FULL_DAY_MINUTES, Vacation, build_vacation

MAX_PLAN_MINUTES = 24 * 60

# 휴가 콤보 항목: (표시 문구, 분). 없음은 None.
VACATION_CHOICES: list[tuple[str, Optional[int]]] = [
    ("없음", None),
    ("2h", 120),
    ("4h", 240),
    ("6h", 360),
    ("8h (1day)", 480),
]


def _hhmm_from_iso(iso: Optional[str]) -> str:
    return iso[11:16] if iso else ""


def parse_recognition_inputs(
    start_text: str, end_text: str
) -> Optional[RecognitionRange]:
    """인정 범위 입력 두 칸을 파싱. 모두 비면 None(해제), 오류 시 ValueError."""
    start_text, end_text = start_text.strip(), end_text.strip()
    if not start_text and not end_text:
        return None
    if not start_text or not end_text:
        raise ValueError("(가)계획은 시작·종료 시각을 모두 입력해야 합니다.")
    return RecognitionRange(
        hhmm_to_minutes(start_text), hhmm_to_minutes(end_text)
    )


def open_day_dialog(
    parent,
    work_date: str,
    clock_in_iso: Optional[str],
    clock_out_iso: Optional[str],
    planned_override: Optional[int],
    default_minutes: int,
    on_save_times: Callable[[str, str, Optional[str]], None],
    on_save_plan: Callable[[str, Optional[int]], None],
    recog_range: Optional[RecognitionRange] = None,
    baseline_minutes: int = 0,
    on_save_recognition: Optional[
        Callable[[str, Optional[RecognitionRange]], None]
    ] = None,
    vacation: Optional[Vacation] = None,
    on_save_vacation: Optional[
        Callable[[str, Optional[Vacation]], None]
    ] = None,
) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"{work_date} 편집")
    layout = QVBoxLayout(dlg)

    form = QFormLayout()
    in_edit = QLineEdit(_hhmm_from_iso(clock_in_iso))
    in_edit.setPlaceholderText("HH:MM")
    out_edit = QLineEdit(_hhmm_from_iso(clock_out_iso))
    out_edit.setPlaceholderText("HH:MM (비우면 미퇴근)")
    plan_edit = QLineEdit("" if planned_override is None else str(planned_override))
    plan_edit.setPlaceholderText(f"분 단위 (비우면 기본 {default_minutes}분)")
    recog_start_edit = QLineEdit(
        "" if recog_range is None else minutes_to_hhmm(recog_range.start_min)
    )
    recog_start_edit.setPlaceholderText("HH:MM (비우면 미설정)")
    recog_end_edit = QLineEdit(
        "" if recog_range is None else minutes_to_hhmm(recog_range.end_min)
    )
    recog_end_edit.setPlaceholderText("HH:MM (비우면 미설정)")
    vacation_combo = QComboBox()
    for label, _minutes in VACATION_CHOICES:
        vacation_combo.addItem(label)
    if vacation is not None:
        for i, (_label, minutes) in enumerate(VACATION_CHOICES):
            if minutes == vacation.minutes:
                vacation_combo.setCurrentIndex(i)
                break
    vacation_start_edit = QLineEdit(
        ""
        if vacation is None or vacation.start_min is None
        else minutes_to_hhmm(vacation.start_min)
    )
    vacation_start_edit.setPlaceholderText("HH:MM (시간제 휴가만)")
    vacation_start_label = QLabel("휴가 시작")
    form.addRow("출근", in_edit)
    form.addRow("퇴근", out_edit)
    form.addRow("실 계획(분)", plan_edit)
    form.addRow("(가)계획 시작", recog_start_edit)
    form.addRow("(가)계획 종료", recog_end_edit)
    form.addRow("휴가", vacation_combo)
    form.addRow(vacation_start_label, vacation_start_edit)
    layout.addLayout(form)

    def _hourly_selected() -> bool:
        """시간제 휴가(2h/4h/6h) 선택 여부. 없음·1day 는 시작 시각 불필요."""
        minutes = VACATION_CHOICES[vacation_combo.currentIndex()][1]
        return minutes is not None and minutes < FULL_DAY_MINUTES

    def _update_vacation_start_visibility() -> None:
        visible = _hourly_selected()
        vacation_start_label.setVisible(visible)
        vacation_start_edit.setVisible(visible)

    vacation_combo.currentIndexChanged.connect(
        lambda _index: _update_vacation_start_visibility()
    )
    _update_vacation_start_visibility()

    buttons = QHBoxLayout()
    cancel = QPushButton("닫기")
    cancel.clicked.connect(dlg.reject)
    save = QPushButton("저장")
    buttons.addWidget(cancel)
    buttons.addWidget(save)
    layout.addLayout(buttons)

    def handle_save() -> None:
        # 1) 계획 파싱 (저장은 검증 통과 후)
        plan_text = plan_edit.text().strip()
        minutes: Optional[int] = None
        if plan_text != "":
            if not plan_text.isdigit():
                QMessageBox.warning(dlg, "입력 오류", "계획은 0 이상 정수(분)여야 합니다.")
                return
            minutes = int(plan_text)
            if minutes > MAX_PLAN_MINUTES:
                QMessageBox.warning(dlg, "입력 오류", "계획은 하루 24시간을 넘을 수 없습니다.")
                return

        # 2) 인정 범위 파싱·검증 (계획을 비우면 기본 계획 기준으로 검증)
        try:
            rng = parse_recognition_inputs(
                recog_start_edit.text(), recog_end_edit.text()
            )
        except ValueError as exc:
            QMessageBox.warning(dlg, "입력 오류", str(exc))
            return
        if rng is not None:
            planned_for_check = minutes if minutes is not None else baseline_minutes
            err = validate_range_against_plan(planned_for_check, rng)
            if err is not None:
                QMessageBox.warning(dlg, "입력 오류", err)
                return

        # 3) 휴가 파싱·검증 (유형 + 시간제면 시작 시각)
        vac_minutes = VACATION_CHOICES[vacation_combo.currentIndex()][1]
        new_vacation: Optional[Vacation] = None
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

        # 4) 검증 통과 → 계획·인정 범위·휴가 저장
        on_save_plan(work_date, minutes)
        if on_save_recognition is not None:
            on_save_recognition(work_date, rng)
        if on_save_vacation is not None:
            on_save_vacation(work_date, new_vacation)

        # 5) 출퇴근 저장 (출근 입력 시에만)
        in_text = in_edit.text().strip()
        if in_text:
            try:
                clock_in = build_iso(work_date, in_text)
                out_text = out_edit.text().strip()
                clock_out = build_iso(work_date, out_text) if out_text else None
                on_save_times(work_date, clock_in, clock_out)
            except ValueError as exc:
                QMessageBox.warning(dlg, "저장 실패", str(exc))
                return
        dlg.accept()

    save.clicked.connect(handle_save)
    dlg.exec()
