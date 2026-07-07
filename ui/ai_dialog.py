"""로컬 AI CLI(Claude Code·Codex) 연동 다이얼로그.

제공자 선택 → 연동 확인(설치·로그인) → 자연어 지시 실행의 흐름.
실행은 QProcess 비동기로 진행하고 출력 로그를 실시간 표시한다.
"""
from __future__ import annotations

import sys
from typing import Callable

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import (
    QColor, QKeySequence, QLinearGradient, QPainter, QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QStyleFactory, QTextEdit, QVBoxLayout, QWidget,
)

import config
from core import timeutil
from core.ai_cli import (
    INSTALL_GUIDES,
    PROVIDER_LABELS,
    build_prompt,
    build_run_command,
    version_command,
)
from ui import theme

_PROVIDER_KEYS = list(PROVIDER_LABELS.keys())


class _RainbowLoadingBar(QWidget):
    """색상이 무지개로 부드럽게 흐르는 얇은 로딩 바.

    네이티브 불확정 QProgressBar 의 끊기는 애니메이션 대신, 매 프레임
    hue 를 조금씩 밀며 그라데이션을 다시 그려 연속적으로 움직인다.
    """

    _HUE_MAX = 360
    _GRADIENT_STOPS = 7
    _SATURATION = 180
    _VALUE = 235

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(theme.AI_LOADING_BAR_H_PX)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(theme.AI_LOADING_TICK_MS)
        self._timer.timeout.connect(self._advance)
        self.setVisible(False)

    def start(self) -> None:
        self.setVisible(True)
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.setVisible(False)

    def _advance(self) -> None:
        self._phase = (self._phase + theme.AI_LOADING_HUE_STEP) % self._HUE_MAX
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), 0)
        for i in range(self._GRADIENT_STOPS):
            t = i / (self._GRADIENT_STOPS - 1)
            hue = int(self._phase + t * self._HUE_MAX) % self._HUE_MAX
            gradient.setColorAt(
                t, QColor.fromHsv(hue, self._SATURATION, self._VALUE)
            )
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        radius = self.height() / 2
        painter.drawRoundedRect(self.rect(), radius, radius)


class _InstructionEdit(QTextEdit):
    """Enter=실행, Shift+Enter=줄바꿈으로 동작하는 지시문 입력 박스."""

    def __init__(self, on_submit) -> None:
        super().__init__()
        self._on_submit = on_submit

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        is_enter = event.key() in (Qt.Key_Return, Qt.Key_Enter)
        if is_enter and not (event.modifiers() & Qt.ShiftModifier):
            self._on_submit()
            return
        super().keyPressEvent(event)


def open_ai_dialog(
    parent, workdir: str, on_applied: Callable[[], None]
) -> None:
    """AI 연동 다이얼로그를 연다. 실행 완료 시 on_applied 로 갱신 통지."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("AI 연동")
    # 처음에는 로그를 숨겨 최소 높이로 시작하고, 실행 시 확장한다
    dlg.setMinimumWidth(theme.AI_DIALOG_MIN_WIDTH)
    layout = QVBoxLayout(dlg)

    workctl_cmd = f"{sys.executable} {workdir}/workctl.py"

    provider_row = QHBoxLayout()
    provider_combo = QComboBox()
    provider_combo.setStyle(QStyleFactory.create("Fusion"))
    for key in _PROVIDER_KEYS:
        provider_combo.addItem(PROVIDER_LABELS[key])
    provider_combo.setCurrentIndex(
        _PROVIDER_KEYS.index(config.get_ai_provider())
    )
    check_btn = QPushButton("연동 확인")
    status_label = QLabel("")
    status_label.setWordWrap(True)
    provider_row.addWidget(QLabel("AI"))
    provider_row.addWidget(provider_combo, stretch=1)
    provider_row.addWidget(check_btn)
    layout.addLayout(provider_row)
    layout.addWidget(status_label)

    close_btn = QPushButton("닫기")
    close_btn.clicked.connect(dlg.reject)
    run_btn = QPushButton("실행")

    instruction_edit = _InstructionEdit(lambda: run_btn.click())
    instruction_edit.setPlaceholderText(
        "예) 다음 주 월~수 실 계획을 6시간으로 바꾸고 금요일에 반차 넣어줘"
        " (Enter=실행, Shift+Enter=줄바꿈)"
    )
    instruction_edit.setFixedHeight(theme.AI_INSTRUCTION_HEIGHT)
    layout.addWidget(instruction_edit)

    # 실행 중 표시용 무지개 로딩 바
    progress = _RainbowLoadingBar()
    layout.addWidget(progress)

    log_view = QTextEdit()
    log_view.setReadOnly(True)
    log_view.setVisible(False)  # 첫 화면에서는 숨김 → 실행 시 표시
    layout.addWidget(log_view, stretch=1)

    buttons = QHBoxLayout()
    buttons.addWidget(close_btn)
    buttons.addWidget(run_btn)
    layout.addLayout(buttons)

    def _provider() -> str:
        return _PROVIDER_KEYS[provider_combo.currentIndex()]

    def _remember_provider() -> None:
        config.set_ai_provider(_provider())

    provider_combo.currentIndexChanged.connect(
        lambda _i: _remember_provider()
    )

    def _set_status(text: str, ok: bool) -> None:
        color = theme.FG_ACTUAL_DONE if ok else theme.FG_RANGE_WARN
        status_label.setStyleSheet(f"color:{color};")
        status_label.setText(text)

    def handle_check() -> None:
        """CLI 설치 여부 확인. 미설치면 설치·로그인 방법 안내."""
        provider = _provider()
        proc = QProcess(dlg)
        proc.start(version_command(provider)[0], version_command(provider)[1:])

        def _done(_code, _status) -> None:
            out = bytes(proc.readAllStandardOutput()).decode(errors="replace")
            if proc.exitCode() == 0 and out.strip():
                _set_status(f"연동 가능: {out.strip()}", ok=True)
            else:
                _set_status(
                    f"CLI 를 찾지 못했습니다. {INSTALL_GUIDES[provider]}",
                    ok=False,
                )

        proc.finished.connect(_done)
        proc.errorOccurred.connect(
            lambda _e: _set_status(
                f"CLI 를 찾지 못했습니다. {INSTALL_GUIDES[provider]}",
                ok=False,
            )
        )

    # 실행 완료(검토) 상태에서만 활성화되는 'r' = 입력모드 복귀 단축키.
    # 입력 중에는 비활성이라 일반 타이핑('r')을 가로채지 않는다.
    reset_shortcut = QShortcut(QKeySequence("R"), dlg)
    reset_shortcut.setEnabled(False)

    def _reset_for_new_input() -> None:
        reset_shortcut.setEnabled(False)
        run_btn.setEnabled(True)
        instruction_edit.setReadOnly(False)
        instruction_edit.clear()
        log_view.clear()
        instruction_edit.setFocus()

    reset_shortcut.activated.connect(_reset_for_new_input)

    def handle_run() -> None:
        instruction = instruction_edit.toPlainText().strip()
        if not instruction:
            QMessageBox.warning(dlg, "입력 오류", "지시할 내용을 입력하세요.")
            return
        prompt = build_prompt(
            instruction, timeutil.today_str(timeutil.now()), workctl_cmd
        )
        cmd = build_run_command(_provider(), prompt, workctl_cmd)
        run_btn.setEnabled(False)
        progress.start()
        if not log_view.isVisible():
            log_view.setVisible(True)
            dlg.resize(dlg.width(), theme.AI_DIALOG_MIN_HEIGHT)
        log_view.clear()

        proc = QProcess(dlg)
        proc.setWorkingDirectory(workdir)
        proc.setProcessChannelMode(QProcess.MergedChannels)

        def _append_output() -> None:
            text = bytes(proc.readAllStandardOutput()).decode(errors="replace")
            log_view.insertPlainText(text)

        def _finished(_code, _status) -> None:
            _append_output()
            done = "완료" if proc.exitCode() == 0 else f"실패 (exit {proc.exitCode()})"
            log_view.insertPlainText(
                f"\n--- {done} ---\n재입력 시, 'r'을 눌러 입력모드로 돌아가세요.\n"
            )
            progress.stop()
            # 결과 검토 상태 — 'r' 로 입력모드 복귀
            instruction_edit.setReadOnly(True)
            reset_shortcut.setEnabled(True)
            on_applied()  # 변경사항을 캘린더에 반영

        proc.readyReadStandardOutput.connect(_append_output)
        proc.finished.connect(_finished)
        proc.errorOccurred.connect(
            lambda _e: (
                log_view.insertPlainText(
                    "\nCLI 실행 실패 — [연동 확인] 으로 설치 상태를 점검하세요.\n"
                ),
                progress.stop(),
                run_btn.setEnabled(True),
            )
        )
        proc.start(cmd[0], cmd[1:])

    check_btn.clicked.connect(handle_check)
    run_btn.clicked.connect(handle_run)
    handle_check()  # 열릴 때 연동 상태 자동 확인
    dlg.exec()
