"""Qt 앱 조립·모드 전환·주기 갱신 컨트롤러."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel

from ui import theme


class AppController:
    def __init__(self) -> None:
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyleSheet(theme.base_stylesheet())
        # TODO(Task 11): MainWindow 로 교체
        self._window = QMainWindow()
        self._window.setWindowTitle("근무시간")
        self._window.setMinimumSize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)
        self._window.setCentralWidget(QLabel("근무시간 앱 (스켈레톤)"))

    def run(self) -> None:
        self._window.show()
        self._app.exec()


def run() -> None:
    AppController().run()
