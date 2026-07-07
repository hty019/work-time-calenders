"""데이터 경로 및 설정 로드/저장."""
from __future__ import annotations

import json
import os

DATA_DIR = os.environ.get(
    "WORK_WIDGET_HOME", os.path.expanduser("~/.work-widget")
)

_SERVICE_KEY_ENV = "DATA_GO_KR_SERVICE_KEY"

DEFAULT_DAILY_MINUTES = 0  # 계획 미설정 시 기본값 없음 (직접 입력)
MODE_FULL = "full"
MODE_WIDGET = "widget"


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


def set_service_key(key: str) -> None:
    cfg = load_config()
    cfg["service_key"] = key
    save_config(cfg)


def get_ai_provider() -> str:
    """AI 연동 제공자 (claude | codex). 기본 claude."""
    provider = load_config().get("ai_provider")
    return provider if provider in ("claude", "codex") else "claude"


def set_ai_provider(provider: str) -> None:
    if provider not in ("claude", "codex"):
        raise ValueError(f"알 수 없는 AI 제공자: {provider!r}")
    cfg = load_config()
    cfg["ai_provider"] = provider
    save_config(cfg)


def get_ai_model(provider: str) -> str | None:
    """제공자별 선택 모델. None 이면 CLI 기본 설정 사용."""
    models = load_config().get("ai_models")
    if isinstance(models, dict) and isinstance(models.get(provider), str):
        return models[provider]
    return None


def set_ai_model(provider: str, model: str | None) -> None:
    cfg = load_config()
    models = cfg.get("ai_models")
    if not isinstance(models, dict):
        models = {}
    models[provider] = model
    cfg["ai_models"] = models
    save_config(cfg)


def get_window_pos() -> tuple[int, int] | None:
    pos = load_config().get("window_pos")
    if isinstance(pos, list) and len(pos) == 2:
        return int(pos[0]), int(pos[1])
    return None


def save_window_pos(x: int, y: int) -> None:
    cfg = load_config()
    cfg["window_pos"] = [x, y]
    save_config(cfg)


def get_default_daily_minutes() -> int:
    value = load_config().get("default_daily_minutes")
    if isinstance(value, int) and value >= 0:
        return value
    return DEFAULT_DAILY_MINUTES


def set_default_daily_minutes(minutes: int) -> None:
    cfg = load_config()
    cfg["default_daily_minutes"] = int(minutes)
    save_config(cfg)


def get_last_mode() -> str:
    mode = load_config().get("last_mode")
    return mode if mode in (MODE_FULL, MODE_WIDGET) else MODE_FULL


def set_last_mode(mode: str) -> None:
    if mode not in (MODE_FULL, MODE_WIDGET):
        raise ValueError(f"알 수 없는 모드: {mode!r}")
    cfg = load_config()
    cfg["last_mode"] = mode
    save_config(cfg)
