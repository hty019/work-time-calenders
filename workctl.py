"""날짜별 기록 조회·편집 CLI — AI 연동 및 수동 관리용.

사용 예 (저장소 루트에서):
  python workctl.py show 2026-07-01 --to 2026-07-07
  python workctl.py set-plan 2026-07-02 360
  python workctl.py clear-plan 2026-07-02
  python workctl.py set-recog 2026-07-02 08:00 20:00
  python workctl.py clear-recog 2026-07-02
  python workctl.py set-vacation 2026-07-02 240 --start 14:00
  python workctl.py clear-vacation 2026-07-02
  python workctl.py set-memo 2026-07-02 "주간 회의"
  python workctl.py clear-memo 2026-07-02

모든 편집 명령은 단일 DATE 대신 범위 옵션을 지원한다:
  --from DATE --to DATE [--weekday 월|...|일] [--skip-holidays]
예) 올해 모든 월요일(공휴일 제외) 실 계획 12h:
  python workctl.py set-plan --from 2026-01-01 --to 2026-12-31 \
      --weekday 월 --skip-holidays 720

출퇴근 시각(실적)은 이 도구로 수정할 수 없다. UI 의 검증 규칙
((가)계획 폭, 휴가 유형, 휴게 재계산)을 동일하게 적용한다.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys

import config
from core.attendance import AttendanceService
from core.holidays import HolidayClient
from core.plan import PlanService
from core.recognition import (
    RecognitionRange,
    RecognitionService,
    hhmm_to_minutes,
    minutes_to_hhmm,
    validate_range_against_plan,
)
from core.storage import Storage
from core.vacation import VacationService, build_vacation

MAX_PLAN_MINUTES = 24 * 60

_WEEKDAY_ALIASES = {
    "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


class _Services:
    def __init__(self) -> None:
        self.storage = Storage(config.db_path())
        self.plans = PlanService(self.storage)
        self.recog = RecognitionService(self.storage)
        self.vacations = VacationService(self.storage)
        self.attendance = AttendanceService(self.storage)
        self.holidays = HolidayClient(
            config.get_service_key(), config.holidays_cache_path()
        )

    def holidays_for(self, date: str) -> dict[str, str]:
        return self.holidays.get_holidays(int(date[:4]), int(date[5:7]))


def _iso_date(text: str) -> str:
    try:
        datetime.date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"잘못된 날짜: {text}") from exc
    return text


def _weekday_index(text: str) -> int:
    key = text.strip().lower()
    if key in _WEEKDAY_ALIASES:
        return _WEEKDAY_ALIASES[key]
    if key.isdigit() and 0 <= int(key) <= 6:
        return int(key)
    raise argparse.ArgumentTypeError(f"잘못된 요일: {text} (월~일 또는 0~6)")


def _resolve_target_dates(
    svc: _Services, args
) -> tuple[list[str] | None, str | None]:
    """단일 DATE 또는 --from/--to 범위(+요일·공휴일 필터)를 날짜 목록으로.

    (dates, 오류 메시지) 를 반환한다.
    """
    single = args.date
    if single is not None:
        if args.date_from or args.date_to:
            return None, "오류: DATE 와 --from/--to 는 함께 쓸 수 없습니다."
        dates = [single]
    else:
        if not args.date_from or not args.date_to:
            return None, "오류: DATE 또는 --from/--to 범위를 지정하세요."
        dates = _dates_between(args.date_from, args.date_to)
    if args.weekday is not None:
        dates = [
            d for d in dates
            if datetime.date.fromisoformat(d).weekday() == args.weekday
        ]
    if args.skip_holidays and args.only_holidays:
        return None, "오류: --skip-holidays 와 --only-holidays 는 함께 쓸 수 없습니다."
    if args.skip_holidays:
        dates = [d for d in dates if d not in svc.holidays_for(d)]
    if args.only_holidays:
        dates = [d for d in dates if d in svc.holidays_for(d)]
    if not dates:
        return None, "오류: 조건에 맞는 날짜가 없습니다."
    return dates, None


def _summary(dates: list[str], action: str) -> str:
    if len(dates) == 1:
        return f"{dates[0]} {action}"
    return f"{action}: {len(dates)}일 ({dates[0]} ~ {dates[-1]})"


def _dates_between(start: str, end: str) -> list[str]:
    d1 = datetime.date.fromisoformat(start)
    d2 = datetime.date.fromisoformat(end)
    if d2 < d1:
        d1, d2 = d2, d1
    return [
        (d1 + datetime.timedelta(days=i)).isoformat()
        for i in range((d2 - d1).days + 1)
    ]


def _day_snapshot(svc: _Services, date: str) -> dict:
    rec = svc.storage.get(date)
    rng = svc.recog.get(date)
    vacation = svc.vacations.get(date)
    return {
        "holiday": svc.holidays_for(date).get(date),
        "clock_in": rec.clock_in if rec else None,
        "clock_out": rec.clock_out if rec else None,
        "work_seconds": rec.work_seconds if rec else None,
        "plan_override": svc.plans.get_override(date),
        "effective_plan_minutes": svc.plans.effective_minutes(
            date, svc.holidays_for(date)
        ),
        "recognition": (
            f"{minutes_to_hhmm(rng.start_min)}~{minutes_to_hhmm(rng.end_min)}"
            if rng else None
        ),
        "vacation_minutes": vacation.minutes if vacation else 0,
        "vacation_start": (
            minutes_to_hhmm(vacation.start_min)
            if vacation and vacation.start_min is not None else None
        ),
        "memo": svc.storage.get_memo(date),
    }


def cmd_show(svc: _Services, args) -> int:
    dates = _dates_between(args.date, args.to or args.date)
    result = {d: _day_snapshot(svc, d) for d in dates}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _validate_recog_width(
    svc: _Services, date: str, minutes: int | None, rng: RecognitionRange
) -> str | None:
    planned = (
        minutes if minutes is not None
        else svc.plans.effective_minutes(date, svc.holidays_for(date))
    )
    return validate_range_against_plan(planned, rng)


def cmd_set_plan(svc: _Services, args) -> int:
    dates, err = _resolve_target_dates(svc, args)
    if err is not None:
        print(err, file=sys.stderr)
        return 1
    if not 0 <= args.minutes <= MAX_PLAN_MINUTES:
        print("오류: 계획은 0~1440분이어야 합니다.", file=sys.stderr)
        return 1
    # 전체 검증 후 일괄 적용 (중간 실패로 일부만 반영되는 것을 방지)
    for date in dates:
        rng = svc.recog.get(date)
        if rng is not None:
            width_err = _validate_recog_width(svc, date, args.minutes, rng)
            if width_err is not None:
                print(f"오류: {date}: {width_err}", file=sys.stderr)
                return 1
    for date in dates:
        svc.plans.set_plan(date, args.minutes)
    print(_summary(dates, f"실 계획 = {args.minutes}분"))
    return 0


def cmd_clear_plan(svc: _Services, args) -> int:
    dates, err = _resolve_target_dates(svc, args)
    if err is not None:
        print(err, file=sys.stderr)
        return 1
    for date in dates:
        svc.plans.clear_plan(date)
    print(_summary(dates, "실 계획 해제(기본값 복귀)"))
    return 0


def cmd_set_recog(svc: _Services, args) -> int:
    dates, err = _resolve_target_dates(svc, args)
    if err is not None:
        print(err, file=sys.stderr)
        return 1
    try:
        rng = RecognitionRange(
            hhmm_to_minutes(args.start), hhmm_to_minutes(args.end)
        )
    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    for date in dates:
        width_err = _validate_recog_width(svc, date, None, rng)
        if width_err is not None:
            print(f"오류: {date}: {width_err}", file=sys.stderr)
            return 1
    for date in dates:
        svc.recog.set(date, rng)
    print(_summary(dates, f"(가)계획 = {args.start}~{args.end}"))
    return 0


def cmd_clear_recog(svc: _Services, args) -> int:
    dates, err = _resolve_target_dates(svc, args)
    if err is not None:
        print(err, file=sys.stderr)
        return 1
    for date in dates:
        svc.recog.clear(date)
    print(_summary(dates, "(가)계획 해제"))
    return 0


def cmd_set_vacation(svc: _Services, args) -> int:
    dates, err = _resolve_target_dates(svc, args)
    if err is not None:
        print(err, file=sys.stderr)
        return 1
    try:
        start_min = hhmm_to_minutes(args.start) if args.start else None
        vacation = build_vacation(args.minutes, start_min=start_min)
    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    for date in dates:
        svc.vacations.set(date, vacation)
        svc.attendance.recompute_work(date)  # 휴가는 근무초에 영향
    print(_summary(dates, f"휴가 = {args.minutes}분"))
    return 0


def cmd_clear_vacation(svc: _Services, args) -> int:
    dates, err = _resolve_target_dates(svc, args)
    if err is not None:
        print(err, file=sys.stderr)
        return 1
    for date in dates:
        svc.vacations.clear(date)
        svc.attendance.recompute_work(date)
    print(_summary(dates, "휴가 해제"))
    return 0


def cmd_set_memo(svc: _Services, args) -> int:
    dates, err = _resolve_target_dates(svc, args)
    if err is not None:
        print(err, file=sys.stderr)
        return 1
    for date in dates:
        svc.storage.set_memo(date, args.text)
    print(_summary(dates, "메모 저장"))
    return 0


def cmd_clear_memo(svc: _Services, args) -> int:
    dates, err = _resolve_target_dates(svc, args)
    if err is not None:
        print(err, file=sys.stderr)
        return 1
    for date in dates:
        svc.storage.set_memo(date, "")
    print(_summary(dates, "메모 삭제"))
    return 0


def _add_edit_target_args(parser: argparse.ArgumentParser) -> None:
    """편집 명령 공통: 단일 DATE 또는 --from/--to 범위(+필터)."""
    parser.add_argument("date", type=_iso_date, nargs="?", default=None)
    parser.add_argument("--from", dest="date_from", type=_iso_date)
    parser.add_argument("--to", dest="date_to", type=_iso_date)
    parser.add_argument(
        "--weekday", type=_weekday_index, default=None,
        help="요일 필터 (월~일 또는 0~6)",
    )
    parser.add_argument(
        "--skip-holidays", action="store_true", help="공휴일 제외"
    )
    parser.add_argument(
        "--only-holidays", action="store_true", help="공휴일만 대상"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workctl", description="근무시간 기록 조회·편집 CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    show = sub.add_parser("show", help="날짜(범위) 기록 JSON 출력")
    show.add_argument("date", type=_iso_date)
    show.add_argument("--to", type=_iso_date, default=None)
    show.set_defaults(func=cmd_show)

    set_plan = sub.add_parser("set-plan", help="실 계획(분) 설정")
    _add_edit_target_args(set_plan)
    set_plan.add_argument("minutes", type=int)
    set_plan.set_defaults(func=cmd_set_plan)

    clear_plan = sub.add_parser("clear-plan", help="실 계획 해제")
    _add_edit_target_args(clear_plan)
    clear_plan.set_defaults(func=cmd_clear_plan)

    set_recog = sub.add_parser("set-recog", help="(가)계획 범위 설정")
    _add_edit_target_args(set_recog)
    set_recog.add_argument("start")
    set_recog.add_argument("end")
    set_recog.set_defaults(func=cmd_set_recog)

    clear_recog = sub.add_parser("clear-recog", help="(가)계획 해제")
    _add_edit_target_args(clear_recog)
    clear_recog.set_defaults(func=cmd_clear_recog)

    set_vac = sub.add_parser(
        "set-vacation", help="휴가 설정 (120/240/360/480분)"
    )
    _add_edit_target_args(set_vac)
    set_vac.add_argument("minutes", type=int)
    set_vac.add_argument("--start", default=None, help="시간제 시작 HH:MM")
    set_vac.set_defaults(func=cmd_set_vacation)

    clear_vac = sub.add_parser("clear-vacation", help="휴가 해제")
    _add_edit_target_args(clear_vac)
    clear_vac.set_defaults(func=cmd_clear_vacation)

    set_memo = sub.add_parser("set-memo", help="메모 저장")
    _add_edit_target_args(set_memo)
    set_memo.add_argument("text")
    set_memo.set_defaults(func=cmd_set_memo)

    clear_memo = sub.add_parser("clear-memo", help="메모 삭제")
    _add_edit_target_args(clear_memo)
    clear_memo.set_defaults(func=cmd_clear_memo)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(_Services(), args)


if __name__ == "__main__":
    sys.exit(main())
