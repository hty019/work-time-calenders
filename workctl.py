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
    if not 0 <= args.minutes <= MAX_PLAN_MINUTES:
        print("오류: 계획은 0~1440분이어야 합니다.", file=sys.stderr)
        return 1
    rng = svc.recog.get(args.date)
    if rng is not None:
        err = _validate_recog_width(svc, args.date, args.minutes, rng)
        if err is not None:
            print(f"오류: {err}", file=sys.stderr)
            return 1
    svc.plans.set_plan(args.date, args.minutes)
    print(f"{args.date} 실 계획 = {args.minutes}분")
    return 0


def cmd_clear_plan(svc: _Services, args) -> int:
    svc.plans.clear_plan(args.date)
    print(f"{args.date} 실 계획 해제(기본값 복귀)")
    return 0


def cmd_set_recog(svc: _Services, args) -> int:
    try:
        rng = RecognitionRange(
            hhmm_to_minutes(args.start), hhmm_to_minutes(args.end)
        )
    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    err = _validate_recog_width(svc, args.date, None, rng)
    if err is not None:
        print(f"오류: {err}", file=sys.stderr)
        return 1
    svc.recog.set(args.date, rng)
    print(f"{args.date} (가)계획 = {args.start}~{args.end}")
    return 0


def cmd_clear_recog(svc: _Services, args) -> int:
    svc.recog.clear(args.date)
    print(f"{args.date} (가)계획 해제")
    return 0


def cmd_set_vacation(svc: _Services, args) -> int:
    try:
        start_min = hhmm_to_minutes(args.start) if args.start else None
        vacation = build_vacation(args.minutes, start_min=start_min)
    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    svc.vacations.set(args.date, vacation)
    svc.attendance.recompute_work(args.date)  # 휴가는 근무초에 영향
    print(f"{args.date} 휴가 = {args.minutes}분")
    return 0


def cmd_clear_vacation(svc: _Services, args) -> int:
    svc.vacations.clear(args.date)
    svc.attendance.recompute_work(args.date)
    print(f"{args.date} 휴가 해제")
    return 0


def cmd_set_memo(svc: _Services, args) -> int:
    svc.storage.set_memo(args.date, args.text)
    print(f"{args.date} 메모 저장")
    return 0


def cmd_clear_memo(svc: _Services, args) -> int:
    svc.storage.set_memo(args.date, "")
    print(f"{args.date} 메모 삭제")
    return 0


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
    set_plan.add_argument("date", type=_iso_date)
    set_plan.add_argument("minutes", type=int)
    set_plan.set_defaults(func=cmd_set_plan)

    clear_plan = sub.add_parser("clear-plan", help="실 계획 해제")
    clear_plan.add_argument("date", type=_iso_date)
    clear_plan.set_defaults(func=cmd_clear_plan)

    set_recog = sub.add_parser("set-recog", help="(가)계획 범위 설정")
    set_recog.add_argument("date", type=_iso_date)
    set_recog.add_argument("start")
    set_recog.add_argument("end")
    set_recog.set_defaults(func=cmd_set_recog)

    clear_recog = sub.add_parser("clear-recog", help="(가)계획 해제")
    clear_recog.add_argument("date", type=_iso_date)
    clear_recog.set_defaults(func=cmd_clear_recog)

    set_vac = sub.add_parser(
        "set-vacation", help="휴가 설정 (120/240/360/480분)"
    )
    set_vac.add_argument("date", type=_iso_date)
    set_vac.add_argument("minutes", type=int)
    set_vac.add_argument("--start", default=None, help="시간제 시작 HH:MM")
    set_vac.set_defaults(func=cmd_set_vacation)

    clear_vac = sub.add_parser("clear-vacation", help="휴가 해제")
    clear_vac.add_argument("date", type=_iso_date)
    clear_vac.set_defaults(func=cmd_clear_vacation)

    set_memo = sub.add_parser("set-memo", help="메모 저장")
    set_memo.add_argument("date", type=_iso_date)
    set_memo.add_argument("text")
    set_memo.set_defaults(func=cmd_set_memo)

    clear_memo = sub.add_parser("clear-memo", help="메모 삭제")
    clear_memo.add_argument("date", type=_iso_date)
    clear_memo.set_defaults(func=cmd_clear_memo)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(_Services(), args)


if __name__ == "__main__":
    sys.exit(main())
