"""공공데이터포털 특일정보 API 공휴일 클라이언트 + 로컬 캐시."""
from __future__ import annotations

import json
import os
from typing import Callable

import requests

_API_URL = (
    "https://apis.data.go.kr/B090041/openapi/service/"
    "SpcdeInfoService/getRestDeInfo"
)
_HTTP_TIMEOUT_SECONDS = 5


def parse_items(items: list[dict], year: int, month: int) -> dict[str, str]:
    """특일정보 item 목록을 {YYYY-MM-DD: 이름} 으로 변환."""
    result: dict[str, str] = {}
    for item in items:
        locdate = str(item.get("locdate", "")).strip()
        if len(locdate) != 8:
            continue
        iso = f"{locdate[0:4]}-{locdate[4:6]}-{locdate[6:8]}"
        result[iso] = item.get("dateName", "공휴일")
    return result


def _http_fetch(service_key: str, year: int, month: int) -> list[dict]:
    params = {
        "serviceKey": service_key,
        "solYear": str(year),
        "solMonth": f"{month:02d}",
        "_type": "json",
        "numOfRows": "100",
    }
    resp = requests.get(_API_URL, params=params, timeout=_HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    body = resp.json()["response"]["body"]
    items = body.get("items")
    if not items:
        return []
    raw = items.get("item", [])
    return raw if isinstance(raw, list) else [raw]


class HolidayClient:
    def __init__(
        self,
        service_key: str | None,
        cache_path: str,
        fetcher: Callable[[str, int, int], list[dict]] | None = None,
    ) -> None:
        self._service_key = service_key
        self._cache_path = cache_path
        self._fetcher = fetcher or _http_fetch

    def _cache_key(self, year: int, month: int) -> str:
        return f"{year:04d}-{month:02d}"

    def _load_cache(self) -> dict:
        if not os.path.exists(self._cache_path):
            return {}
        try:
            with open(self._cache_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_cache(self, cache: dict) -> None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self._cache_path)), exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except OSError:
            # 캐시 저장은 best-effort: 디스크 부족, 권한 오류 등을 무시
            return

    def get_holidays(self, year: int, month: int) -> dict[str, str]:
        key = self._cache_key(year, month)
        cache = self._load_cache()
        if key in cache:
            return cache[key]
        if not self._service_key:
            return {}
        try:
            items = self._fetcher(self._service_key, year, month)
        except Exception:
            return cache.get(key, {})
        holidays = parse_items(items, year, month)
        cache[key] = holidays
        self._save_cache(cache)
        return holidays
