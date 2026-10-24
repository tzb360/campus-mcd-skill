from datetime import date
from pathlib import Path

import pytest

from campus_mcd.calendar import free_windows
from campus_mcd.planner import plan
from campus_mcd.report import public_view, render


def test_ics_window():
    windows = free_windows(Path("examples/timetable.ics").read_bytes(), date(2026, 10, 24))
    assert any(w["minutes"] == 90 and "12:00:00+08:00" in w["start"] for w in windows)


def test_ics_recurrence_not_silently_ignored():
    data = (
        Path("examples/timetable.ics")
        .read_bytes()
        .replace(b"SUMMARY:", b"RRULE:FREQ=WEEKLY\nSUMMARY:", 1)
    )
    with pytest.raises(ValueError, match="单次"):
        free_windows(data, date(2026, 10, 24))


def test_ics_private_titles_not_output():
    data = (
        Path("examples/timetable.ics").read_bytes().replace("模拟课程一".encode(), b"secret-class")
    )
    assert "secret-class" not in str(free_windows(data, date(2026, 10, 24)))


def test_ics_size():
    with pytest.raises(ValueError):
        free_windows(b"a" * 1_000_001, date(2026, 10, 24))


def test_public_report_privacy_and_xss(request_value, snapshot):
    snapshot.stores[0].name = "private-exact-store"
    snapshot.offers[1].name = '<img src=x onerror="alert(1)">'
    result = plan(request_value, snapshot)
    content = render(result)
    assert "private-exact-store" not in content
    assert "<img src=x" not in content
    assert "&lt;img" in content
    assert "2026-10-24T" not in content
    assert "模拟数据" in content
    assert "private-exact-store" in render(result, private_details=True)
    assert all("quote_at" not in o["choice"] for o in public_view(result)["options"])


def test_no_report_savings_invented(request_value, snapshot):
    for o in snapshot.offers:
        o.baseline_cents = None
    assert "无同单对照" in render(plan(request_value, snapshot))
