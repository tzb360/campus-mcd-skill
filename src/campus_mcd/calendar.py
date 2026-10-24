from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from icalendar import Calendar


def free_windows(
    data: bytes,
    day: date,
    zone: str = "Asia/Shanghai",
    opening: time = time(8),
    closing: time = time(22),
) -> list[dict]:
    if len(data) > 1_000_000:
        raise ValueError("ICS超过1MB上限")
    tz = ZoneInfo(zone)
    low, high = datetime.combine(day, opening, tz), datetime.combine(day, closing, tz)
    busy = []
    events = Calendar.from_ical(data).walk("VEVENT")
    if len(events) > 2000:
        raise ValueError("ICS超过2000事件上限")
    for event in events:
        if (
            str(event.get("STATUS", "")).upper() == "CANCELLED"
            or str(event.get("TRANSP", "")).upper() == "TRANSPARENT"
        ):
            continue
        if any(key in event for key in ("RRULE", "RDATE", "EXDATE", "RECURRENCE-ID")):
            raise ValueError(
                "MVP仅支持展开后的单次VEVENT；请先从课表导出已展开日期，未忽略循环事件"
            )
        begin = event.decoded("DTSTART")
        finish = event.decoded("DTEND", None)
        if finish is None:
            duration = event.decoded("DURATION", None)
            if duration is None:
                raise ValueError("事件缺少DTEND/DURATION")
            finish = begin + duration
        if not isinstance(begin, datetime):
            begin = datetime.combine(begin, time.min, tz)
        if not isinstance(finish, datetime):
            finish = datetime.combine(finish, time.min, tz)
        begin = begin.replace(tzinfo=tz) if begin.tzinfo is None else begin.astimezone(tz)
        finish = finish.replace(tzinfo=tz) if finish.tzinfo is None else finish.astimezone(tz)
        if finish <= begin:
            raise ValueError("ICS事件结束时间异常")
        if begin < high and finish > low:
            busy.append((max(low, begin), min(high, finish)))
    cursor, free = low, []
    for begin, finish in sorted(busy):
        if begin > cursor:
            free.append(
                {
                    "start": cursor.isoformat(),
                    "deadline": begin.isoformat(),
                    "minutes": int((begin - cursor).total_seconds() // 60),
                }
            )
        cursor = max(cursor, finish)
    if cursor < high:
        free.append(
            {
                "start": cursor.isoformat(),
                "deadline": high.isoformat(),
                "minutes": int((high - cursor).total_seconds() // 60),
            }
        )
    return free
