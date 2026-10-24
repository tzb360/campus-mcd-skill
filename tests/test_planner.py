from datetime import timedelta

import pytest
from pydantic import ValidationError

from campus_mcd.models import Request, Snapshot
from campus_mcd.planner import plan


def test_three_policies_and_roundtrip(request_value, snapshot):
    r = plan(request_value, snapshot)
    a, b, c = [x["choice"] for x in r["options"]]
    assert a["payable_cents"] == 1390
    assert b["minutes"] == 34  # 4*2 walking + 6 assumed wait + 15 eating + 5 buffer
    assert a["savings_cents"] == 600
    assert a["minutes"] == 39
    assert c["payable_cents"] <= request_value.budget_cents
    assert r["evaluated_count"] == 5 and r["candidate_count"] == 4


def test_too_short_never_promises(request_value, snapshot):
    request_value.deadline = request_value.start + timedelta(minutes=25)
    r = plan(request_value, snapshot)
    assert r["candidate_count"] == 0
    assert all(o["choice"] is None for o in r["options"])


def test_low_budget_no_fabricated_deal(request_value, snapshot):
    request_value.budget_cents = 100
    assert plan(request_value, snapshot)["candidate_count"] == 0


def test_kcal_unknown_and_over_limit_excluded(request_value, snapshot):
    request_value.max_kcal = 700
    snapshot.offers[0].kcal = None
    r = plan(request_value, snapshot)
    assert r["candidate_count"] == 2
    assert all(x["choice"]["kcal"] <= 700 for x in r["options"])


def test_avoid_and_preference(request_value, snapshot):
    request_value.avoid = ["牛肉"]
    request_value.prefer = ["鸡肉"]
    r = plan(request_value, snapshot)
    assert all("双堡" not in x["choice"]["meal"] for x in r["options"])


def test_unknown_times_fail_closed(request_value, snapshot):
    for s in snapshot.stores:
        s.wait_minutes = None
    assert plan(request_value, snapshot)["candidate_count"] == 0


def test_walk_limit_and_available_window(request_value, snapshot):
    request_value.max_walk_minutes = 4
    request_value.available_minutes = 34
    r = plan(request_value, snapshot)
    assert r["candidate_count"] == 2
    assert all(o["choice"]["slack_minutes"] == 0 for o in r["options"])


def test_expired_coupons_excluded(request_value, snapshot):
    for o in snapshot.offers:
        o.expires_at = request_value.start - timedelta(seconds=1)
    assert plan(request_value, snapshot)["candidate_count"] == 0


def test_no_savings_without_actual_baseline(request_value, snapshot):
    request_value.max_walk_minutes = 4
    r = plan(request_value, snapshot)
    assert r["options"][0]["choice"]["savings_cents"] is None


def test_empty_menu(request_value, snapshot):
    snapshot.offers = []
    assert plan(request_value, snapshot)["evaluated_count"] == 0


def test_live_old_quote_and_late_start(request_value, snapshot):
    snapshot.mode = "live"
    now = request_value.start + timedelta(minutes=10)
    assert plan(request_value, snapshot, now)["candidate_count"] == 0
    for o in snapshot.offers:
        o.quote_at = now
    r = plan(request_value, snapshot, now)
    assert r["window_minutes"] == 80
    assert all(o["choice"]["depart_at"] == now.isoformat() for o in r["options"])


@pytest.mark.parametrize(
    "changes",
    [
        {"start": "2026-10-24T12:00:00"},
        {"deadline": "2026-10-24T11:00:00+08:00"},
        {"budget_cents": 25.5},
        {"budget_cents": -1},
        {"budget_cents": True},
        {"buffer_minutes": -1},
        {"max_kcal": 0},
        {"available_minutes": 0},
        {"unknown": "x"},
    ],
)
def test_invalid_request_rejected(data, changes):
    with pytest.raises(ValidationError):
        Request.model_validate(data["requests"]["lunch"] | changes)


def test_bounded_and_referential_snapshot(data):
    raw = data["snapshot"]
    raw["offers"][0]["store_id"] = "unknown"
    with pytest.raises(ValidationError):
        Snapshot.model_validate(raw)
    raw["offers"][0]["store_id"] = "demo-a"
    raw["offers"] *= 3
    with pytest.raises(ValidationError):
        Snapshot.model_validate(raw)
