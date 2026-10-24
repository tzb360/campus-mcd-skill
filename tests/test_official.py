"""Synthetic shapes derived from discovered schema; NO real account fixtures."""

from unittest.mock import AsyncMock

import pytest
from mcp.types import CallToolResult

from campus_mcd.mcp_client import McpFailure
from campus_mcd.official import (
    automatic,
    compose,
    modification,
    nutrition_table,
    quote_price,
    success,
)


def ok(data):
    return {"success": True, "code": 200, "data": data}


@pytest.mark.parametrize(
    "value", [{"success": False, "code": 200}, {"success": True, "code": 500}, {}]
)
def test_business_success_is_required(value):
    with pytest.raises(McpFailure):
        success(value)


def test_tabular_nutrition_exact_and_conflicting_rows():
    text = '[3]{productName,energyKcal}:\n  测试鸡肉堡,400\n  测试鸡肉堡,420\n  "测试,玉米",50'
    table = nutrition_table(text)
    assert table["测试鸡肉堡"] is None
    assert table["测试,玉米"] == 50


@pytest.mark.parametrize(
    "text", ["x", "[2]{productName,energyKcal}:\n a,1", "[1]{name,energyKcal}:\n a,1"]
)
def test_unknown_nutrition_format_fails_closed(text):
    with pytest.raises(ValueError):
        nutrition_table(text)


def test_modification_includes_unselected_keys():
    detail = {
        "modification": {
            "items": [
                {
                    "minValues": 0,
                    "maxValues": 2,
                    "values": [
                        {
                            "code": "a",
                            "selectedQuantity": 1,
                            "selectedKey": "yes",
                            "unselectedKey": "no",
                        },
                        {
                            "code": "b",
                            "selectedQuantity": 0,
                            "selectedKey": "yes",
                            "unselectedKey": "no",
                        },
                    ],
                }
            ]
        }
    }
    assert modification(detail)["values"] == [
        {"code": "a", "key": "yes", "quantity": 1},
        {"code": "b", "key": "no", "quantity": 0},
    ]


def test_incomplete_required_modification_not_guessed():
    with pytest.raises(ValueError):
        modification({"modification": {"items": [{"minValues": 1, "maxValues": 1, "values": []}]}})


def test_combo_nutrition_is_complete_basket(request_value):
    request_value.max_kcal = 700
    request_value.prefer = ["鸡肉"]

    def choice(code, name, default):
        return {"code": code, "name": name, "isDefault": default, "maxQuantity": -1}

    detail = {
        "code": "combo",
        "name": "测试套餐",
        "rounds": [
            {
                "id": 1,
                "quantity": 1,
                "minQuantity": 1,
                "choices": [choice("a", "未知鸡肉堡", 1), choice("b", "测试鸡肉堡", 0)],
            },
            {"id": 2, "quantity": 1, "minQuantity": 1, "choices": [choice("c", "玉米", 1)]},
        ],
    }
    item, label, kcal, tags = compose(detail, request_value, {"测试鸡肉堡": 400, "玉米": 50})
    assert kcal == 450
    assert item["roundList"][0]["comboItemList"][0]["code"] == "b"
    assert "鸡肉" in tags and "玉米" in label
    assert compose(detail, request_value, {"测试鸡肉堡": 400})[2] is None


@pytest.mark.parametrize(
    "quote",
    [
        {"price": 0, "productList": []},
        {"price": 100, "productList": [{"productCode": "other", "quantity": 1}]},
        {"price": True, "productList": []},
    ],
)
def test_empty_or_different_quote_is_not_a_free_meal(quote):
    with pytest.raises(McpFailure):
        quote_price(quote, [{"productCode": "meal", "quantity": 1}])


async def test_gateway_rejects_real_observed_empty_basket():
    from campus_mcd.mcp_client import Gateway

    gateway = Gateway(AsyncMock(), {"calculate-price": {"inputSchema": {"type": "object"}}})
    gateway.session.call_tool.return_value = CallToolResult(
        content=[], structuredContent=ok({"price": 0, "productList": []})
    )
    with pytest.raises(McpFailure) as error:
        await gateway.call("calculate-price", {"basket": "test"})
    assert error.value.code == "business"


async def test_automatic_end_to_end_with_coupon_baseline_invalid(request_value):
    nutrition = "[1]{productName,energyKcal}:\n 测试鸡腿堡,400"
    calls = []

    async def call(name, args):
        calls.append((name, args))
        if name == "query-nearby-stores":
            return ok([{"storeCode": "s1", "storeName": "测试店", "businessStatus": True}])
        if name == "list-nutrition-foods":
            return ok(nutrition)
        if name == "query-my-coupons":
            return ok({"coupons": [{"id": "owned", "enable": 1}]})
        if name == "campaign-calendar":
            return ok({})
        if name == "query-meals":
            return ok({"meals": {"m1": {"name": "测试鸡腿堡", "currentPrice": "15"}}})
        if name == "query-store-coupons":
            return ok(
                [
                    {
                        "couponId": "owned",
                        "tradeDateTime": "2026-01-01 00:00:00 - 2026-12-31 23:59:59",
                        "couponCode": "test-only",
                        "products": [{"productCode": "m1", "productName": "测试鸡腿堡"}],
                    }
                ]
            )
        if name == "query-meal-detail":
            return ok({"code": "m1", "name": "测试鸡腿堡", "rounds": []})
        if name == "calculate-price":
            if "couponId" not in args["items"][0]:
                raise McpFailure("business", "empty baseline")
            return ok({"price": 1000, "productList": [{"productCode": "m1", "quantity": 1}]})
        raise AssertionError(name)

    gateway = AsyncMock()
    gateway.call = call
    snap = await automatic(
        request_value,
        gateway,
        city="测试城市",
        keyword="测试校园",
        walks=[5],
        wait=8,
        store_limit=1,
    )
    assert snap.mode == "live" and len(snap.offers) == 1
    assert snap.offers[0].payable_cents == 1000 and snap.offers[0].baseline_cents is None
    assert len(calls) == 9
    assert any("无券对照" in warning for warning in snap.warnings)


async def test_automatic_bad_time_arguments_fail_before_network(request_value):
    gateway = AsyncMock()
    with pytest.raises(ValueError):
        await automatic(
            request_value, gateway, city="x", keyword="x", walks=[-1], wait=8, store_limit=1
        )
    gateway.call.assert_not_called()


def test_coupon_expiry_format_is_explicit():
    from campus_mcd.official import coupon_window

    assert coupon_window("tomorrow") is None
    assert coupon_window("2026-10-25 00:00:00 - 2026-10-24 00:00:00") is None
    window = coupon_window("2026-10-24 00:00:00 - 2026-10-25 23:59:59")
    assert window[1].utcoffset().total_seconds() == 28800
    assert coupon_window("2026-10-24 00:00:00-2026-10-25 23:59:59") is not None
