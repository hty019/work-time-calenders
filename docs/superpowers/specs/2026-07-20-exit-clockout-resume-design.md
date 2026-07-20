# 종료 시 자동 퇴근 · 재실행 시 자동 재개 설계

작성일: 2026-07-20

## 목적

프로그램을 정상 종료하면 그 시점으로 오늘의 퇴근을 저장해 근무 기록이 진행
중인 채로 방치되지 않게 하고, 같은 날 다시 실행하면 그 자동 퇴근을 취소해
근무시간이 연속으로 이어지게 한다. 강제 종료(SIGKILL 등)는 처리 대상이 아니다.

## 요구사항

1. **정상 종료 시 자동 퇴근**
   - 종료 시점에 오늘이 **진행 중(WORKING: 출근 기록 있고 퇴근 없음)** 이면 현재
     시각으로 퇴근을 저장한다.
   - 이미 **수동 퇴근**(CLOCKED_OUT)했거나 미출근이면 아무것도 하지 않는다.
   - 자동 퇴근을 저장한 경우에만 "자동 종료 퇴근 마커"를 남긴다.
2. **재실행 시 자동 재개**
   - 마커가 **오늘 날짜**이고 오늘 퇴근 기록이 있으면 그 퇴근을 취소해 진행
     중으로 되돌린다(원래 출근 시각 기준 연속 누적 — 종료~재실행 사이 자리비운
     간격도 근무로 포함).
   - **자동 종료 퇴근만** 재개한다. 사용자가 직접 [퇴근] 버튼을 눌러 마감한
     날은 마커가 없으므로 재개하지 않는다.
   - 마커가 다른 날(어제 등)이면 재개하지 않는다(그 날은 자동 퇴근으로 정상
     마감된 상태로 유지).
   - 부팅 처리 후 마커는 항상 비운다(소비 또는 stale 무효화). 이후 같은 세션에서
     다시 종료하면 마커를 재기록한다.

## 구분 방식 (자동 vs 수동)

`config.json` 에 `auto_clock_out_date`(YYYY-MM-DD 또는 없음) 마커를 둔다.
attendance 테이블 스키마는 변경하지 않는다 — 재개 판정은 "같은 날 1건"만
필요하므로 단일 마커로 충분하다.

## 동작 흐름

```
[정상 종료] QApplication.aboutToQuit
  rec = service.auto_clock_out()          # WORKING 일 때만 record_clock_out
  if rec is not None:
      config.set_auto_clock_out_date(rec.work_date)

[재실행]  AppController.run()
  service.record_clock_in()               # 멱등: 오늘 기록 있으면 유지
  service.resume_auto_clock_out(config.get_auto_clock_out_date())
  config.set_auto_clock_out_date(None)    # 마커 비움(소비/무효화)
  ... 기존 refresh/timer/exec
```

## 컴포넌트

### core/attendance.py — AttendanceService 메서드 2개 (Qt 비의존, TDD)

```python
def auto_clock_out(self) -> Attendance | None:
    """진행 중(WORKING)일 때만 현재 시각으로 퇴근 저장. 그 외 None.

    미출근(기록 없음)·이미 퇴근(수동 포함)이면 건드리지 않는다.
    """
    now = self._clock()
    date = timeutil.today_str(now)
    existing = self._storage.get(date)
    if existing is None or existing.clock_out is not None:
        return None
    return self.record_clock_out()

def resume_auto_clock_out(self, marker_date: str | None) -> Attendance | None:
    """marker_date 가 오늘이고 오늘 퇴근 기록이 있으면 취소해 재개.

    그 외(마커 없음·다른 날·이미 진행 중)에는 아무것도 하지 않고 None.
    """
    now = self._clock()
    date = timeutil.today_str(now)
    if marker_date != date:
        return None
    return self.cancel_clock_out()
```
- `record_clock_out`/`cancel_clock_out` 는 기존 메서드 재사용(휴가 반영 work_seconds
  계산·취소 로직 그대로).

### config.py — 마커 get/set

```python
def get_auto_clock_out_date() -> str | None:
    return load_config().get("auto_clock_out_date")

def set_auto_clock_out_date(date: str | None) -> None:
    cfg = load_config()
    if date is None:
        cfg.pop("auto_clock_out_date", None)
    else:
        cfg["auto_clock_out_date"] = date
    save_config(cfg)
```

### ui/app.py — 배선

- `AppController.__init__` 또는 `run()` 에서
  `self._app.aboutToQuit.connect(self._handle_app_exit)` 연결.
- `_handle_app_exit`:
  ```python
  def _handle_app_exit(self) -> None:
      rec = self._service.auto_clock_out()
      if rec is not None:
          config.set_auto_clock_out_date(rec.work_date)
  ```
- `run()` 의 `record_clock_in()` 직후, `_refresh()` 이전에 재개+마커 비움:
  ```python
  self._service.record_clock_in()
  self._service.resume_auto_clock_out(config.get_auto_clock_out_date())
  config.set_auto_clock_out_date(None)
  ```

## 엣지 케이스

- **자동 종료 → 재개 → 수동 퇴근 → 종료 → 재실행**: 재개 시 마커를 비우므로,
  이후 수동 퇴근 후 종료하면 `auto_clock_out` 이 CLOCKED_OUT 을 보고 skip(마커
  미기록) → 재실행 시 수동 퇴근 유지. ✅
- **자동 종료 후 날을 넘겨 재실행**: 오늘(새 날짜) 기록 없음 → 신규 출근. 마커는
  어제라 재개 안 함, 어제 자동 퇴근은 정상 마감으로 유지, 마커만 비움. ✅
- **강제 종료**: `aboutToQuit` 미발생 → 퇴근 미저장(진행 중 방치). 사용자 수용.
- **위젯/전체 모드 무관**: 판정은 오늘 기록 기준이라 두 모드 모두 동일.

## 테스트 (core TDD)

### tests/test_attendance.py 추가 (실 Storage + 고정 clock)
1. `auto_clock_out`: WORKING → 퇴근 저장(clock_out 설정·work_seconds 계산).
2. `auto_clock_out`: 미출근(기록 없음) → None, 기록 미생성.
3. `auto_clock_out`: 이미 퇴근(수동) → None, 기존 clock_out 시각 불변(덮어쓰지 않음).
4. `resume_auto_clock_out`: 마커==오늘 & 퇴근 있음 → 취소(진행 중 복귀).
5. `resume_auto_clock_out`: 마커==오늘 & 퇴근 없음(진행 중) → None(변화 없음).
6. `resume_auto_clock_out`: 마커!=오늘(어제) → None(오늘 기록 불변).
7. `resume_auto_clock_out`: 마커 None → None.

### tests/test_config.py 추가
8. `set_auto_clock_out_date`/`get_auto_clock_out_date` 왕복, None 이면 키 제거.

Qt 종료 훅(`aboutToQuit`)·`run()` 배선은 헤드리스 검증 불가 → import·회귀
테스트까지만, 실제 종료/재실행 동작은 사용자 확인.

## 비목표 (YAGNI)

- 강제 종료 대응(시그널 핸들러·주기적 하트비트 저장) — 요청 범위 밖.
- 자리비운 간격 제외(공백 차감) — 연속 누적으로 확정.
- attendance 스키마 변경 — 단일 config 마커로 충분.
