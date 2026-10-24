from unittest.mock import AsyncMock

import pytest

from campus_mcd.live import LiveRecipe, cents, execute, pointer
from campus_mcd.mcp_client import Gateway, McpFailure


def binding(call, path):
    return {"call": call, "pointer": path}


@pytest.fixture
def recipe():
    calls = []
    for ref, tool, args in [
        ("stores", "query-nearby-stores", {}),
        ("detail", "query-meal-detail", {}),
        ("pay", "calculate-price", {"store": "s1", "meal": "m1"}),
    ]:
        calls.append(
            {
                "id": ref,
                "tool": tool,
                "arguments": args,
                "assertions": [{"pointer": "/ok", "equals": True}],
            }
        )
    return LiveRecipe(
        calls=calls,
        stores=[
            {
                "id": binding("stores", "/id"),
                "name": binding("stores", "/name"),
                "walk_minutes": 4,
                "walk_basis": "用户估算",
                "wait_minutes": 5,
                "wait_basis": "用户假设",
            }
        ],
        offers=[
            {
                "id": "o1",
                "store_id": "s1",
                "name": binding("detail", "/name"),
                "meal_id": binding("detail", "/id"),
                "unit": "yuan",
                "payable": binding("pay", "/total"),
                "tags": ["鸡肉"],
            }
        ],
    )


@pytest.fixture
def gateway():
    session = AsyncMock()
    tools = {
        n: {"inputSchema": {"type": "object"}}
        for n in ["query-nearby-stores", "query-meal-detail", "calculate-price"]
    }
    return Gateway(session, tools)


async def test_recipe_uses_fresh_quote_not_agent_literal(recipe, gateway):
    gateway.call = AsyncMock(
        side_effect=[
            {"ok": True, "id": "s1", "name": "Store"},
            {"ok": True, "id": "m1", "name": "Meal"},
            {"ok": True, "total": "18.80"},
        ]
    )
    result = await execute(recipe, gateway)
    assert result.mode == "live" and result.offers[0].payable_cents == 1880
    assert result.offers[0].baseline_cents is None


async def test_business_rejection_does_not_become_free_meal(recipe, gateway):
    gateway.call = AsyncMock(return_value={"ok": False, "total": 0})
    with pytest.raises(McpFailure) as error:
        await execute(recipe, gateway)
    assert error.value.code == "business"


async def test_price_cannot_come_from_menu(recipe, gateway):
    recipe.offers[0]["payable"] = binding("detail", "/total")
    gateway.call = AsyncMock(
        side_effect=[
            {"ok": True, "id": "s1", "name": "Store"},
            {"ok": True, "id": "m1", "name": "Meal", "total": 0},
            {"ok": True, "total": 18},
        ]
    )
    with pytest.raises(ValueError, match="来源"):
        await execute(recipe, gateway)


async def test_different_basket_cannot_claim_savings(recipe, gateway):
    recipe.calls.append(
        {
            "id": "base",
            "tool": "calculate-price",
            "arguments": {"store": "s2", "meal": "m1"},
            "assertions": [{"pointer": "/ok", "equals": True}],
        }
    )
    recipe.offers[0].update(baseline=binding("base", "/total"), coupon_argument_paths=["/coupon"])
    gateway.call = AsyncMock(
        side_effect=[
            {"ok": True, "id": "s1", "name": "Store"},
            {"ok": True, "id": "m1", "name": "Meal"},
            {"ok": True, "total": 18},
            {"ok": True, "total": 22},
        ]
    )
    with pytest.raises(ValueError, match="同店"):
        await execute(recipe, gateway)


async def test_preflight_blocks_mutation_without_calls(recipe, gateway):
    recipe.calls[-1]["tool"] = "create-order"
    gateway.tools["create-order"] = {"inputSchema": {"type": "object"}}
    gateway.call = AsyncMock()
    with pytest.raises(McpFailure) as error:
        await execute(recipe, gateway)
    assert error.value.code == "blocked"
    gateway.call.assert_not_called()


@pytest.mark.parametrize(
    "value,unit",
    [("nan", "yuan"), ("1.001", "yuan"), (-1, "cents"), (True, "cents"), (10, "unknown")],
)
def test_bad_money(value, unit):
    with pytest.raises(ValueError):
        cents(value, unit)


def test_json_pointer_escaping():
    assert pointer({"a/b": {"~x": [4]}}, "/a~1b/~0x/0") == 4
