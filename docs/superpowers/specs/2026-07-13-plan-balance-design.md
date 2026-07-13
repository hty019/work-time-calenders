# 실 계획 대비 누적 여유/부족분 표시

## 목적

STATUS 패널의 진행도 캡션(`근로 시간 진행도: 72%`)에 완료된 과거 일자의
**실 계획 대비 실제 근무 시간의 누적 여유/부족분**을 병기한다. 사용자가 이번 달
계획 이행 속도(앞서 있는지 뒤처져 있는지)를 한눈에 파악하도록 한다.

예: `근로 시간 진행도: 72% (+2h 30m)` — 여유는 녹색, 부족은 빨강.

## 결정 사항

- **집계 범위**: 오늘 이전(`date < today`)의 완료된 과거 일자만. 오늘은 진행
  중이라 계획이 만료되지 않았으므로 제외.
- **미기록 과거 평일**: 실 계획은 있으나 출근 기록이 없는 날은 실제 근무 0으로
  보고 실 계획 전액을 부족분으로 계산.

## 집계 로직 (core/stats.py)

순수 함수 신설:

```
plan_balance_seconds(storage, plan_service, holidays, year, month, today) -> int
```

- 그 달 1일부터 말일까지 순회하되 `date < today` 인 날만 집계.
- 각 날에 대해:
  - 실 계획초 = `plan_service.effective_minutes(date, holidays)` × 60
  - 실제 근무초 = `(rec.work_seconds or 0)` + `휴가분 × 60`
    (월 누적 `actual_seconds` 와 동일하게 휴가를 근로로 합산)
  - 누적 += (실제 근무초 − 실 계획초)
- 부호 있는 초(int) 반환.

### 경계·상쇄 규칙

- 주말·평일 공휴일: 실 계획 0 → 영향 없음.
- 1day 휴가일: 실 계획(평일 기본 8h) vs 휴가 8h → 상쇄되어 0.
- 미기록 과거 평일: 실제 0 − 실 계획 8h → −8h 부족.
- 미래 달 조회: `date < today` 대상이 없음 → 0.
- 과거 달 조회: 모든 날이 `< today` → 전부 집계.

## 연결 (MonthSummary)

- `MonthSummary` 에 `plan_balance_seconds: int = 0` 필드 추가.
- `build_month_summary` 에서 `plan_balance_seconds(...)` 결과로 채운다.

## 표시 (ui/status_panel.py)

- `progress_caption` 이 기존 캡션 뒤에 색상 조각을 병기(QLabel 리치텍스트).
- 형식은 기존 `format_hm` 재사용 → `+2h 30m` / `-1h 15m`.
- 부호별 색상: 여유(+) 녹색 `FG_SURPLUS`, 부족(−) 빨강 `FG_DEFICIT`.
- 0이면 부호 없이 muted `(±0)`.
- 법정 초과 캡션(`초과 근로 진행: +Nh`)에도 동일하게 병기 — 여유/부족은 진행도
  단계와 독립적인 정보이므로 항상 표시.

## 색상 토큰 (ui/theme.py)

- `FG_SURPLUS = "#4ade80"` (녹색, 여유)
- `FG_DEFICIT = "#ff5a5a"` (빨강, 부족)

## 테스트

- **core** (`tests/`): 여유, 부족, 미기록일 부족 반영, 휴가 상쇄, 오늘 제외,
  주말/공휴일 무영향, 미래 달 0, 과거 달 전량 집계.
- **ui**: `progress_caption` 포맷·색상 병기(양수/음수/0), 법정 초과 캡션 병기.
