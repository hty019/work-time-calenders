"""공휴일 API 인증키 등록 다이얼로그."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout,
)

from ui import theme


def open_api_key_dialog(
    parent,
    on_test: Callable[[str], tuple[bool, str]],
    on_save: Callable[[str], None],
) -> None:
    """인증키(Decoding) 를 입력받아 테스트·등록한다.

    on_test 는 (성공 여부, 안내 메시지) 를 반환하고,
    on_save 는 등록 확정 시 키를 저장한다.
    """
    dlg = QDialog(parent)
    dlg.setWindowTitle("공휴일 API 키 등록")
    dlg.setMinimumWidth(theme.API_KEY_DIALOG_MIN_WIDTH)
    layout = QVBoxLayout(dlg)

    info = QLabel(
        "공공데이터포털 '한국천문연구원 특일 정보' 서비스의\n"
        "일반 인증키(Decoding) 를 입력하세요."
    )
    layout.addWidget(info)

    key_edit = QLineEdit()
    key_edit.setPlaceholderText("일반 인증키 (Decoding)")
    layout.addWidget(key_edit)

    test_row = QHBoxLayout()
    test_btn = QPushButton("테스트")
    result_label = QLabel("")
    result_label.setWordWrap(True)
    test_row.addWidget(test_btn)
    test_row.addWidget(result_label, stretch=1)
    layout.addLayout(test_row)

    buttons = QHBoxLayout()
    cancel_btn = QPushButton("취소")
    cancel_btn.clicked.connect(dlg.reject)
    save_btn = QPushButton("등록")
    buttons.addWidget(cancel_btn)
    buttons.addWidget(save_btn)
    layout.addLayout(buttons)

    def current_key() -> str | None:
        key = key_edit.text().strip()
        if not key:
            QMessageBox.warning(dlg, "입력 오류", "인증키를 입력하세요.")
            return None
        return key

    def handle_test() -> None:
        key = current_key()
        if key is None:
            return
        test_btn.setEnabled(False)
        result_label.setStyleSheet(f"color:{theme.FG_MUTED};")
        result_label.setText("호출 확인 중…")
        # 아래 on_test 가 블로킹 네트워크 호출이므로 라벨 갱신을 먼저 반영
        QApplication.processEvents()
        ok, msg = on_test(key)
        color = theme.FG_ACTUAL_DONE if ok else theme.FG_RANGE_WARN
        result_label.setStyleSheet(f"color:{color};")
        result_label.setText(msg)
        test_btn.setEnabled(True)

    def handle_save() -> None:
        key = current_key()
        if key is None:
            return
        on_save(key)
        dlg.accept()

    test_btn.clicked.connect(handle_test)
    save_btn.clicked.connect(handle_save)
    dlg.exec()
