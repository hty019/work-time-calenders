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


def test_get_holidays_falls_back_to_cache_on_fetch_error(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({"2026-06": {"2026-06-06": "현충일"}}), encoding="utf-8")

    def boom(key, year, month):
        raise RuntimeError("network down")

    client = HolidayClient("KEY", str(cache), fetcher=boom)
    assert client.get_holidays(2026, 6) == {"2026-06-06": "현충일"}
