"""데이터 경로 및 설정 로드/저장."""
from __future__ import annotations

import json
import os

DATA_DIR = os.environ.get(
    "WORK_WIDGET_HOME", os.path.expanduser("~/.work-widget")
)

_SERVICE_KEY_ENV = "DATA_GO_KR_SERVICE_KEY"


def db_path() -> str:
    return os.path.join(DATA_DIR, "attendance.db")


def holidays_cache_path() -> str:
    return os.path.join(DATA_DIR, "holidays_cache.json")


def config_path() -> str:
    return os.path.join(DATA_DIR, "config.json")


def load_config() -> dict:
    path = config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_service_key() -> str | None:
    env = os.environ.get(_SERVICE_KEY_ENV)
    if env:
        return env
    return load_config().get("service_key")


def get_window_pos() -> tuple[int, int] | None:
    pos = load_config().get("window_pos")
    if isinstance(pos, list) and len(pos) == 2:
        return int(pos[0]), int(pos[1])
    return None


def save_window_pos(x: int, y: int) -> None:
    cfg = load_config()
    cfg["window_pos"] = [x, y]
    save_config(cfg)
