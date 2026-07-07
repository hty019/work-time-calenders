"""로컬 AI CLI(Claude Code·Codex) 연동 다이얼로그.

제공자 선택 → 연동 확인(설치·로그인) → 자연어 지시 실행의 흐름.
실행은 QProcess 비동기로 진행하고 출력 로그를 실시간 표시한다.
"""
from __future__ import annotations

import os
import sys
from typing import Callable

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import (
    QColor, QKeySequence, QLinearGradient, QPainter, QShortcut, QTextCursor,
)
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QStyleFactory, QTextEdit, QVBoxLayout, QWidget,
)

import config
from core import timeutil
from core.ai_cli import (
    AUTH_LOGGED_OUT,
    AUTH_READY,
    INSTALL_GUIDES,
    MODEL_CHOICES,
    PROVIDER_LABELS,
    auth_status_command,
    build_prompt,
    build_run_command,
    format_stream_event,
    login_command,
    login_terminal_command,
    parse_auth_status,
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

    # 허용 패턴(접두사 일치)과 AI 가 실행할 명령이 정확히 같아지도록
    # 작업 폴더 기준 상대 경로의 짧은 표준형을 쓴다
    python_cmd = os.path.relpath(sys.executable, workdir)
    if python_cmd.startswith(".."):
        python_cmd = sys.executable  # venv 밖 실행 등 예외 시 절대 경로
    workctl_cmd = f"{python_cmd} workctl.py"
    running_procs: list[QProcess] = []

    provider_row = QHBoxLayout()
    provider_combo = QComboBox()
    provider_combo.setStyle(QStyleFactory.create("Fusion"))
    for key in _PROVIDER_KEYS:
        provider_combo.addItem(PROVIDER_LABELS[key])
    provider_combo.setCurrentIndex(
        _PROVIDER_KEYS.index(config.get_ai_provider())
    )
    model_combo = QComboBox()
    model_combo.setStyle(QStyleFactory.create("Fusion"))
    check_btn = QPushButton("연동 확인")
    # 로그인이 필요할 때만 노출되는 버튼 (새 터미널에서 대화형 로그인)
    login_btn = QPushButton("로그인")
    login_btn.setVisible(False)
    status_label = QLabel("")
    status_label.setWordWrap(True)
    provider_row.addWidget(QLabel("AI"))
    provider_row.addWidget(provider_combo, stretch=1)
    provider_row.addWidget(model_combo, stretch=1)
    provider_row.addWidget(check_btn)
    provider_row.addWidget(login_btn)
    layout.addLayout(provider_row)
    layout.addWidget(status_label)

    close_btn = QPushButton("닫기")
    close_btn.clicked.connect(dlg.reject)

    instruction_edit = _InstructionEdit(lambda: handle_run())
    instruction_edit.setPlaceholderText(
        "예) 다음 주 월~수 실 계획을 6시간으로 바꾸고 금요일에 반차 넣어줘"
        " (Enter=실행, Shift+Enter=줄바꿈)"
    )
    instruction_edit.setFixedHeight(theme.AI_INSTRUCTION_HEIGHT)
    layout.addWidget(instruction_edit)

    # 실행 중 표시용 무지개 로딩 바
    progress = _RainbowLoadingBar()
    layout.addWidget(progress)

    # 실행 중에는 진행 로그(실행 명령·중간 텍스트)를 스트리밍 표시하고,
    # 완료 시 AI 최종 응답을 하단에 덧붙인다. 최대 N줄 높이로 제한하고
    # 넘치는 내용은 내부 스크롤로 확인한다.
    log_view = QTextEdit()
    log_view.setReadOnly(True)
    log_view.setVisible(False)
    line_height = log_view.fontMetrics().lineSpacing()
    log_view.setFixedHeight(
        line_height * theme.AI_LOG_MAX_LINES
        + int(log_view.document().documentMargin()) * 2
        + log_view.frameWidth() * 2
    )
    layout.addWidget(log_view)

    buttons = QHBoxLayout()
    buttons.addWidget(close_btn)
    layout.addLayout(buttons)

    def _show_log_area() -> None:
        if not log_view.isVisible():
            log_view.setVisible(True)
            QTimer.singleShot(
                0, lambda: dlg.resize(dlg.width(), dlg.sizeHint().height())
            )

    def _provider() -> str:
        return _PROVIDER_KEYS[provider_combo.currentIndex()]

    def _current_model() -> str | None:
        return MODEL_CHOICES[_provider()][model_combo.currentIndex()][1]

    def _reload_models() -> None:
        """제공자에 맞는 모델 목록으로 갱신하고 저장된 선택을 복원."""
        saved = config.get_ai_model(_provider())
        model_combo.blockSignals(True)
        model_combo.clear()
        selected = 0
        for i, (label, value) in enumerate(MODEL_CHOICES[_provider()]):
            model_combo.addItem(label)
            if value == saved:
                selected = i
        model_combo.setCurrentIndex(selected)
        model_combo.blockSignals(False)

    def _on_provider_changed() -> None:
        config.set_ai_provider(_provider())
        _reload_models()
        handle_check()  # 제공자별 로그인 상태를 다시 확인

    provider_combo.currentIndexChanged.connect(
        lambda _i: _on_provider_changed()
    )
    model_combo.currentIndexChanged.connect(
        lambda _i: config.set_ai_model(_provider(), _current_model())
    )
    _reload_models()

    def _set_status(text: str, ok: bool) -> None:
        color = theme.FG_ACTUAL_DONE if ok else theme.FG_RANGE_WARN
        status_label.setStyleSheet(f"color:{color};")
        status_label.setText(text)

    def _check_version_fallback(provider: str) -> None:
        """로그인 상태를 판정 못하면(구버전 등) 설치 여부라도 확인한다."""
        proc = QProcess(dlg)

        def _done(_code, _status) -> None:
            out = bytes(proc.readAllStandardOutput()).decode(errors="replace")
            if proc.exitCode() == 0 and out.strip():
                _set_status(
                    f"설치됨: {out.strip()} — 로그인 상태를 확인할 수 없습니다."
                    " 실행이 인증 오류로 실패하면 [로그인] 을 누르세요.",
                    ok=True,
                )
                login_btn.setVisible(True)
            else:
                _set_status(
                    f"CLI 를 찾지 못했습니다. {INSTALL_GUIDES[provider]}",
                    ok=False,
                )
                login_btn.setVisible(False)

        proc.finished.connect(_done)
        proc.errorOccurred.connect(
            lambda _e: (
                _set_status(
                    f"CLI 를 찾지 못했습니다. {INSTALL_GUIDES[provider]}",
                    ok=False,
                ),
                login_btn.setVisible(False),
            )
        )
        proc.start(version_command(provider)[0], version_command(provider)[1:])

    def handle_check() -> None:
        """CLI 설치·로그인 상태 확인. 미로그인이면 [로그인] 버튼을 노출한다."""
        provider = _provider()
        proc = QProcess(dlg)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        args = auth_status_command(provider)

        def _done(_code, _status) -> None:
            out = bytes(proc.readAllStandardOutput()).decode(errors="replace")
            status = parse_auth_status(provider, proc.exitCode(), out)
            if status == AUTH_READY:
                _set_status("로그인 완료 — AI 실행이 가능합니다.", ok=True)
                login_btn.setVisible(False)
            elif status == AUTH_LOGGED_OUT:
                _set_status(
                    "로그인이 필요합니다. [로그인] 을 눌러 진행하세요.",
                    ok=False,
                )
                login_btn.setVisible(True)
            else:
                # auth 상태를 못 읽으면(미지원 등) 설치 여부로 대체 확인
                _check_version_fallback(provider)

        proc.finished.connect(_done)
        # 바이너리 미설치 시 finished 는 오지 않으므로 여기서 설치 안내
        proc.errorOccurred.connect(
            lambda _e: _check_version_fallback(provider)
        )
        proc.start(args[0], args[1:])
        proc.closeWriteChannel()

    def handle_login() -> None:
        """새 터미널에서 대화형 로그인(브라우저 OAuth)을 시작한다."""
        provider = _provider()
        cmd = login_terminal_command(provider)
        # PySide6 는 (성공여부, pid) 튜플을 돌려주므로 첫 값만 본다
        started, _pid = QProcess.startDetached(cmd[0], cmd[1:])
        if started:
            _set_status(
                "새 터미널에서 로그인을 진행하세요. 완료 후 [연동 확인] 을"
                " 다시 누르면 상태가 갱신됩니다.",
                ok=True,
            )
        else:
            manual = " ".join(login_command(provider))
            _set_status(
                f"터미널을 열지 못했습니다. 직접 터미널에서 '{manual}' 를"
                " 실행해 로그인하세요.",
                ok=False,
            )

    # 실행 완료(검토) 상태에서만 활성화되는 입력모드 복귀 단축키.
    # 한글 자판(ㄱ)도 함께 등록하고, 입력 중에는 비활성이라 일반
    # 타이핑을 가로채지 않는다.
    reset_shortcuts = [
        QShortcut(QKeySequence(key), dlg) for key in ("R", "ㄱ")
    ]
    for shortcut in reset_shortcuts:
        shortcut.setEnabled(False)

    def _set_reset_enabled(enabled: bool) -> None:
        for shortcut in reset_shortcuts:
            shortcut.setEnabled(enabled)

    def _reset_for_new_input() -> None:
        _set_reset_enabled(False)
        instruction_edit.setReadOnly(False)
        instruction_edit.clear()
        log_view.clear()
        log_view.setVisible(False)  # 첫 화면과 동일한 최소 높이로 복귀
        QTimer.singleShot(
            0, lambda: dlg.resize(dlg.width(), dlg.sizeHint().height())
        )
        instruction_edit.setFocus()

    for shortcut in reset_shortcuts:
        shortcut.activated.connect(_reset_for_new_input)

    def handle_run() -> None:
        if instruction_edit.isReadOnly():
            return  # 실행 중이거나 결과 검토 상태 — Enter 무시
        instruction = instruction_edit.toPlainText().strip()
        if not instruction:
            QMessageBox.warning(dlg, "입력 오류", "지시할 내용을 입력하세요.")
            return
        prompt = build_prompt(
            instruction, timeutil.today_str(timeutil.now()), workctl_cmd
        )
        provider = _provider()
        cmd = build_run_command(
            provider, prompt, workctl_cmd, model=_current_model()
        )
        instruction_edit.setReadOnly(True)  # 실행 중 재입력 방지
        progress.start()
        log_view.clear()
        _show_log_area()  # 진행 로그를 실시간으로 보여준다

        proc = QProcess(dlg)
        proc.setWorkingDirectory(workdir)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        pending = {"buffer": ""}  # 줄 단위 파싱용 미완성 라인 버퍼

        def _append_line(text: str) -> None:
            # 사용자가 로그를 클릭해 커서가 옮겨져도 항상 문서 끝에 덧붙인다
            log_view.moveCursor(QTextCursor.End)
            log_view.insertPlainText(text + "\n")
            log_view.verticalScrollBar().setValue(
                log_view.verticalScrollBar().maximum()
            )

        def _append_output() -> None:
            chunk = bytes(proc.readAllStandardOutput()).decode(errors="replace")
            pending["buffer"] += chunk
            *lines, pending["buffer"] = pending["buffer"].split("\n")
            for line in lines:
                text = format_stream_event(provider, line)
                if text is not None:
                    _append_line(text)

        def _finished(_code, _status) -> None:
            _append_output()
            leftover = format_stream_event(provider, pending["buffer"])
            if leftover is not None:
                _append_line(leftover)
            pending["buffer"] = ""
            done = "완료" if proc.exitCode() == 0 else f"실패 (exit {proc.exitCode()})"
            _append_line(
                f"\n--- {done} ---\n재입력 시, 'r'을 눌러 입력모드로 돌아가세요."
            )
            progress.stop()
            # 결과 검토 상태 — 'r'/'ㄱ' 로 입력모드 복귀
            _set_reset_enabled(True)
            on_applied()  # 변경사항을 캘린더에 반영

        proc.readyReadStandardOutput.connect(_append_output)
        proc.finished.connect(_finished)
        proc.errorOccurred.connect(
            lambda _e: (
                _append_line(
                    "\nCLI 실행 실패 — [연동 확인] 으로 설치 상태를 점검하세요."
                ),
                progress.stop(),
                instruction_edit.setReadOnly(False),
            )
        )
        running_procs.append(proc)
        proc.start(cmd[0], cmd[1:])
        # 파이프 입력 대기(경고·지연)를 막기 위해 stdin 을 즉시 닫는다
        proc.closeWriteChannel()

    def _kill_running() -> None:
        """다이얼로그를 닫으면 실행 중인 AI 프로세스도 함께 종료한다."""
        for proc in running_procs:
            if proc.state() != QProcess.NotRunning:
                proc.kill()

    dlg.finished.connect(lambda _result: _kill_running())

    check_btn.clicked.connect(handle_check)
    login_btn.clicked.connect(handle_login)
    handle_check()  # 열릴 때 연동 상태 자동 확인
    dlg.exec()
