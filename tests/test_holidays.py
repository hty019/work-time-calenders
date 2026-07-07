import json

import requests

import core.holidays as holidays_mod
from core.holidays import HolidayClient, parse_items


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._payload


def test_http_fetch_retries_on_intermittent_401(monkeypatch):
    """게이트웨이의 간헐적 401은 재시도로 흡수되어야 한다."""
    monkeypatch.setattr(holidays_mod.time, "sleep", lambda _s: None)
    ok_payload = {
        "response": {
            "body": {"items": {"item": {"locdate": 20260606, "dateName": "현충일"}}}
        }
    }
    calls = {"n": 0}

    def flaky_get(url, params, timeout):
        calls["n"] += 1
        if calls["n"] < 3:  # 처음 두 번은 401
            return _FakeResponse(401)
        return _FakeResponse(200, ok_payload)

    monkeypatch.setattr(holidays_mod.requests, "get", flaky_get)
    items = holidays_mod._http_fetch("KEY", 2026, 6)
    assert items == [{"locdate": 20260606, "dateName": "현충일"}]
    assert calls["n"] == 3


def test_http_fetch_raises_after_exhausting_retries(monkeypatch):
    """모든 재시도가 401이면 최종적으로 예외를 던진다(상위에서 fallback 처리)."""
    monkeypatch.setattr(holidays_mod.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        holidays_mod.requests, "get",
        lambda url, params, timeout: _FakeResponse(401),
    )
    try:
        holidays_mod._http_fetch("KEY", 2026, 6)
        assert False, "예외가 발생해야 한다"
    except requests.HTTPError:
        pass


def test_parse_items_converts_locdate():
    items = [
        {"locdate": 20260606, "dateName": "현충일"},
        {"locdate": 20260615, "dateName": "임시공휴일"},
    ]
    result = parse_items(items, 2026, 6)
    assert result == {"2026-06-06": "현충일", "2026-06-15": "임시공휴일"}


def test_get_holidays_uses_fetcher_and_caches(tmp_path):
    cache = tmp_path / "cache.json"
    calls = []

    def fake_fetch(key, year, month):
        calls.append((year, month))
        return [{"locdate": 20260606, "dateName": "현충일"}]

    client = HolidayClient("KEY", str(cache), fetcher=fake_fetch)
    first = client.get_holidays(2026, 6)
    assert first == {"2026-06-06": "현충일"}
    # 두 번째 호출은 캐시 사용 → fetcher 재호출 없음
    second = client.get_holidays(2026, 6)
    assert second == {"2026-06-06": "현충일"}
    assert calls == [(2026, 6)]


def test_get_holidays_without_key_returns_fixed_offline_holidays(tmp_path):
    """키가 없어도 양력 고정 공휴일은 오프라인 기본값으로 표시된다."""
    client = HolidayClient(None, str(tmp_path / "c.json"))
    # 6월엔 현충일(6/6)이 고정 공휴일로 존재
    assert client.get_holidays(2026, 6) == {"2026-06-06": "현충일"}
    # 7월엔 양력 고정 공휴일이 없음
    assert client.get_holidays(2026, 7) == {}


def test_get_holidays_merges_api_over_fixed(tmp_path):
    """API 결과가 오프라인 고정 공휴일과 합쳐지고, 같은 날짜는 API가 우선한다."""
    cache = tmp_path / "cache.json"

    def fake_fetch(key, year, month):
        return [{"locdate": 20261005, "dateName": "추석"}]

    client = HolidayClient("KEY", str(cache), fetcher=fake_fetch)
    result = client.get_holidays(2026, 10)
    # 고정(개천절·한글날) + API(추석)가 모두 포함된다
    assert result == {
        "2026-10-03": "개천절",
        "2026-10-09": "한글날",
        "2026-10-05": "추석",
    }


def test_get_holidays_cache_first_skips_fetcher(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"2026-06": {"2026-06-06": "현충일"}}), encoding="utf-8")

    def boom(key, year, month):
        raise RuntimeError("network down")

    client = HolidayClient("KEY", str(cache), fetcher=boom)
    assert client.get_holidays(2026, 6) == {"2026-06-06": "현충일"}


def test_get_holidays_fetch_error_falls_back_to_offline(tmp_path):
    """fetch 실패 + 빈 캐시 시 raise 하지 않고 오프라인 고정 공휴일을 반환."""
    cache = tmp_path / "cache.json"

    def boom(key, year, month):
        raise RuntimeError("network down")

    client = HolidayClient("KEY", str(cache), fetcher=boom)
    # 6월은 현충일이 오프라인 기본값으로 남는다
    assert client.get_holidays(2026, 6) == {"2026-06-06": "현충일"}
    # 7월은 고정 공휴일이 없어 빈 dict
    assert client.get_holidays(2026, 7) == {}


def test_save_cache_failure_does_not_raise(tmp_path):
    """캐시 저장 실패 시에도 get_holidays는 raise 하지 않고 parsed dict 반환."""
    # 캐시 경로를 생성 불가능한 경로로 설정 (부모 디렉토리가 파일)
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("")  # 파일로 생성
    impossible_cache = str(cache_file / "subdir" / "cache.json")  # 파일 아래 경로

    def fake_fetch(key, year, month):
        return [{"locdate": 20260606, "dateName": "현충일"}]

    client = HolidayClient("KEY", impossible_cache, fetcher=fake_fetch)
    result = client.get_holidays(2026, 6)
    # 캐시 저장은 실패했지만 parsed holidays는 반환됨
    assert result == {"2026-06-06": "현충일"}


def test_verify_service_key_success_reports_count():
    ok, msg = holidays_mod.verify_service_key(
        "KEY", 2026, 7,
        fetcher=lambda k, y, m: [{"locdate": 20260815, "dateName": "광복절"}],
    )
    assert ok is True
    assert "1건" in msg


def test_verify_service_key_request_error_fails():
    def fetcher(_k, _y, _m):
        raise requests.HTTPError("401 Unauthorized")

    ok, msg = holidays_mod.verify_service_key("KEY", 2026, 7, fetcher=fetcher)
    assert ok is False
    assert "401" in msg


def test_verify_service_key_parse_error_mentions_key_check():
    """잘못된 키로 XML 오류 응답이 오면 JSON 해석이 실패한다 — 키 확인 안내."""
    def fetcher(_k, _y, _m):
        raise ValueError("Expecting value")

    ok, msg = holidays_mod.verify_service_key("KEY", 2026, 7, fetcher=fetcher)
    assert ok is False
    assert "인증키" in msg


def test_verify_service_key_calls_api_only_once(monkeypatch):
    """키 테스트는 재시도 없이 단일 호출로 즉시 결과를 보여야 한다."""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(1)
        return _FakeResponse(401)

    monkeypatch.setattr(holidays_mod.requests, "get", fake_get)
    ok, msg = holidays_mod.verify_service_key("KEY", 2026, 7)
    assert ok is False
    assert len(calls) == 1
