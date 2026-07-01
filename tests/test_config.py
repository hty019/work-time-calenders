import importlib
import os


def load_config_module(tmp_path, monkeypatch):
    monkeypatch.setenv("WORK_WIDGET_HOME", str(tmp_path))
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    import config as config_module

    importlib.reload(config_module)
    return config_module


def test_paths_under_data_dir(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    assert cfg.db_path() == os.path.join(str(tmp_path), "attendance.db")
    assert cfg.holidays_cache_path() == os.path.join(
        str(tmp_path), "holidays_cache.json"
    )


def test_service_key_env_takes_priority(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    cfg.save_config({"service_key": "FROM_FILE"})
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "FROM_ENV")
    assert cfg.get_service_key() == "FROM_ENV"


def test_service_key_falls_back_to_file(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    cfg.save_config({"service_key": "FROM_FILE"})
    assert cfg.get_service_key() == "FROM_FILE"


def test_window_pos_roundtrip(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    assert cfg.get_window_pos() is None
    cfg.save_window_pos(100, 200)
    assert cfg.get_window_pos() == (100, 200)


def test_default_daily_minutes_roundtrip(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    assert cfg.get_default_daily_minutes() == cfg.DEFAULT_DAILY_MINUTES
    cfg.set_default_daily_minutes(240)
    assert cfg.get_default_daily_minutes() == 240


def test_last_mode_roundtrip(tmp_path, monkeypatch):
    cfg = load_config_module(tmp_path, monkeypatch)
    assert cfg.get_last_mode() == cfg.MODE_FULL
    cfg.set_last_mode(cfg.MODE_WIDGET)
    assert cfg.get_last_mode() == cfg.MODE_WIDGET
