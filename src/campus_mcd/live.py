"""Agent-authored bindings, runtime-discovered schemas, fresh official quotes.

JSON pointers are deliberately explicit: the public McD docs don't publish schemas.
No undocumented field names are assumed by the Python planner.
"""

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .mcp_client import McpFailure
from .models import Model, Offer, Snapshot, Store


class LiveRecipe(Model):
    calls: list[dict]
    stores: list[dict]
    offers: list[dict]


def pointer(data, path):
    if path == "":
        return data
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("JSON Pointer必须为空或以/开头")
    for part in path[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def sourced(binding, results, names, allowed=None):
    if set(binding) != {"call", "pointer"}:
        raise ValueError("来源映射只允许call与pointer")
    ref = binding["call"]
    if allowed and names[ref] not in allowed:
        raise ValueError("字段来源工具不符合约束")
    return pointer(results[ref], binding["pointer"])


def cents(value, unit):
    if isinstance(value, bool) or unit not in {"yuan", "cents"}:
        raise ValueError("报价必须明确单位yuan或cents")
    try:
        value = Decimal(str(value)) * (100 if unit == "yuan" else 1)
    except InvalidOperation:
        raise ValueError("报价不是数值") from None
    if not value.is_finite() or value < 0 or value != value.to_integral_value():
        raise ValueError("报价不能为负数、非数或包含不足一分的尾数")
    return int(value)


def without_paths(arguments, paths):
    copy = deepcopy(arguments)
    for path in paths:
        parent_path, _, key = path.rpartition("/")
        if not key:
            raise ValueError("优惠参数路径无效")
        parent = pointer(copy, parent_path)
        # Only object properties may be removed; never drop products from an array.
        if not isinstance(parent, dict):
            raise ValueError("优惠参数只能是对象属性")
        parent.pop(key.replace("~1", "/").replace("~0", "~"), None)
    return copy


def contains_identifier(value, identifier):
    if isinstance(value, dict):
        return any(contains_identifier(v, identifier) for v in value.values())
    if isinstance(value, list):
        return any(contains_identifier(v, identifier) for v in value)
    return str(value) == str(identifier)


async def execute(recipe: LiveRecipe, gateway):
    if not 1 <= len(recipe.calls) <= 32 or len(recipe.offers) > 12 or len(recipe.stores) > 3:
        raise ValueError("配方超过3店、12候选或32调用上限")
    results, names, arguments, stamps = {}, {}, {}, {}
    quote_count = sum(c.get("tool") == "calculate-price" for c in recipe.calls)
    if quote_count > 12:
        raise ValueError("单轮最多12次整单试算（含无券对照）")
    # Preflight the entire batch before any network tool calls.
    for call in recipe.calls:
        if set(call) != {"id", "tool", "arguments", "assertions"} or not call["assertions"]:
            raise ValueError(
                "每次调用需要id/tool/arguments/非空assertions；按真实响应声明业务成功条件"
            )
        ref = call["id"]
        if ref in names:
            raise ValueError("调用ID重复")
        names[ref] = call["tool"]
        arguments[ref] = call["arguments"]
        if call["tool"] not in gateway.tools:
            raise McpFailure("missing_tool", "配方包含未发现工具，请重新发现")
        gateway.validate(call["tool"], call["arguments"])
        for assertion in call["assertions"]:
            if set(assertion) != {"pointer", "equals"}:
                raise ValueError("assertions使用pointer与equals")
    for call in recipe.calls:
        result = await gateway.call(call["tool"], call["arguments"])
        for assertion in call["assertions"]:
            if pointer(result, assertion["pointer"]) != assertion["equals"]:
                raise McpFailure(
                    "business", "业务成功条件不成立，可能菜单为空、售罄或券不适用；未采用本轮报价"
                )
        results[call["id"]] = result
        stamps[call["id"]] = datetime.now(timezone.utc)
    stores = []
    for spec in recipe.stores:
        value = dict(spec)
        for field in ("id", "name"):
            value[field] = str(sourced(spec[field], results, names, {"query-nearby-stores"}))
        if value.get("walk_minutes") is not None and not value.get("walk_basis"):
            raise ValueError("步行估算须说明依据")
        if value.get("wait_minutes") is not None and not value.get("wait_basis"):
            raise ValueError("出餐估算须说明依据；不能宣称实时排队")
        stores.append(Store.model_validate(value))
    offers = []
    for spec in recipe.offers:
        quote_ref = spec["payable"]["call"]
        price = sourced(spec["payable"], results, names, {"calculate-price"})
        meal_id = sourced(spec["meal_id"], results, names, {"query-meals", "query-meal-detail"})
        if (
            not str(meal_id).strip()
            or not contains_identifier(arguments[quote_ref], meal_id)
            or not contains_identifier(arguments[quote_ref], spec["store_id"])
        ):
            raise ValueError("报价请求必须包含实际来源的餐品与门店编码；不能把另一单报价用于本候选")
        baseline = None
        if spec.get("baseline"):
            baseline_ref = spec["baseline"]["call"]
            baseline = cents(
                sourced(spec["baseline"], results, names, {"calculate-price"}), spec["unit"]
            )
            if not contains_identifier(arguments[baseline_ref], meal_id) or not contains_identifier(
                arguments[baseline_ref], spec["store_id"]
            ):
                raise ValueError("对照报价不是同店同餐品")
            paths = spec.get("coupon_argument_paths", [])
            if not paths or without_paths(arguments[quote_ref], paths) != without_paths(
                arguments[baseline_ref], paths
            ):
                raise ValueError("节省金额要求同店同商品同规格同取餐方式，仅优惠参数可不同")
        meal_ref = spec["name"]["call"]
        name = sourced(spec["name"], results, names, {"query-meals", "query-meal-detail"})
        # Tags are agent interpretation; require a detail query for the relevant basket.
        if names[meal_ref] != "query-meal-detail" and spec.get("tags"):
            raise ValueError("偏好标签需要query-meal-detail来源，不能只看菜单标题")
        kcal = None
        if spec.get("kcal"):
            kcal = sourced(spec["kcal"], results, names, {"list-nutrition-foods"})
            if isinstance(kcal, bool):
                raise ValueError("热量不能是布尔值")
            try:
                kcal = float(Decimal(str(kcal)))
            except InvalidOperation:
                raise ValueError("热量必须是明确的千卡数值") from None
        coupon = None
        if spec.get("coupon"):
            coupon = str(
                sourced(spec["coupon"], results, names, {"query-store-coupons", "query-my-coupons"})
            )
        offers.append(
            Offer(
                id=spec["id"],
                store_id=spec["store_id"],
                name=str(name),
                payable_cents=cents(price, spec["unit"]),
                baseline_cents=baseline,
                kcal=kcal,
                tags=spec.get("tags", []),
                coupon=coupon,
                quote_at=stamps[quote_ref],
                expires_at=(
                    sourced(
                        spec["expires_at"],
                        results,
                        names,
                        {"query-store-coupons", "query-my-coupons", "calculate-price"},
                    )
                    if spec.get("expires_at")
                    else None
                ),
                evidence=f"calculate-price:{quote_ref}; 本轮即时调用，字段映射由Agent解释",
            )
        )
    return Snapshot(
        mode="live",
        stores=stores,
        offers=offers,
        warnings=[
            "MCP不提供可靠实时路况与排队保证；时间依赖用户确认的估算。",
            "价格仅为本轮整单试算，不锁价；未来时段用餐需临近出发重新核价。",
        ],
    )
