import json

from core.holidays import HolidayClient, parse_items


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


def test_get_holidays_returns_empty_without_key(tmp_path):
    client = HolidayClient(None, str(tmp_path / "c.json"))
    assert client.get_holidays(2026, 6) == {}


def test_get_holidays_cache_first_skips_fetcher(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"2026-06": {"2026-06-06": "현충일"}}), encoding="utf-8")

    def boom(key, year, month):
        raise RuntimeError("network down")

    client = HolidayClient("KEY", str(cache), fetcher=boom)
    assert client.get_holidays(2026, 6) == {"2026-06-06": "현충일"}


def test_get_holidays_fetch_error_empty_cache_returns_empty(tmp_path):
    """fetch 실패 + 빈 캐시 시 empty dict 반환하고 raise 하지 않음."""
    cache = tmp_path / "cache.json"

    def boom(key, year, month):
        raise RuntimeError("network down")

    client = HolidayClient("KEY", str(cache), fetcher=boom)
    result = client.get_holidays(2026, 6)
    assert result == {}


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
