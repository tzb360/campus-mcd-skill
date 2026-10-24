"""McD response adapter, verified against tools/list and read-only calls on 2026-10-24.

Unknown shapes stop the adapter. The generic recipe command remains available for
Agent-controlled mappings. Menu prices ONLY bound candidate selection, never the result.
"""

import csv
import io
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from .mcp_client import McpFailure
from .models import Offer, Request, Snapshot, Store


def success(result):
    if (
        not isinstance(result, dict)
        or result.get("success") is not True
        or result.get("code") != 200
    ):
        raise McpFailure("business", "官方工具业务未成功，未采用报价；请重新查询或检查参数")
    return result["data"]


def normalize(name):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", name))


def nutrition_table(text):
    """Strictly parse the observed tabular TOON format; unknown formats fail closed."""
    if not isinstance(text, str) or len(text) > 300000:
        raise ValueError("营养格式未知")
    lines = text.strip().splitlines()
    header = re.fullmatch(r"\[(\d+)\]\{([^}]+)\}:", lines[0]) if lines else None
    if not header:
        raise ValueError("营养格式已变化；需要Agent适配")
    columns = header[2].split(",")
    if "productName" not in columns or "energyKcal" not in columns:
        raise ValueError("营养表缺少餐品名或千卡字段")
    rows = list(csv.reader(io.StringIO("\n".join(line.strip() for line in lines[1:]))))
    if len(rows) != int(header[1]) or any(len(row) != len(columns) for row in rows):
        raise ValueError("营养行数或字段数量不符")
    table = {}
    for row in rows:
        value = dict(zip(columns, row))
        try:
            kcal = Decimal(value["energyKcal"])
        except InvalidOperation:
            continue
        if not kcal.is_finite() or kcal < 0 or kcal > 10000:
            continue
        key = normalize(value["productName"])
        # Duplicate conflicting nutrition rows are not silently overwritten.
        if key in table and table[key] != float(kcal):
            table[key] = None
        else:
            table[key] = float(kcal)
    return table


def modification(entity):
    values = []
    for group in entity.get("modification", {}).get("items", []):
        selected = 0
        for item in group.get("values", []):
            quantity = item.get("selectedQuantity", 0)
            if not isinstance(quantity, int) or quantity < 0:
                raise ValueError("特调默认数量无效")
            if quantity:
                key = item["selectedKey"]
                selected += 1
            else:
                key = item.get("unselectedKey")
            if key:
                values.append({"code": item["code"], "key": key, "quantity": quantity})
        if not group.get("minValues", 0) <= selected <= group.get("maxValues", selected):
            raise ValueError("特调默认选择不完整；需Agent手动处理")
    return {"values": values} if values else None


def tags_for(names):
    joined = " ".join(names)
    tags = []
    for tag, terms in {
        "鸡肉": ("鸡",),
        "牛肉": ("牛", "巨无霸"),
        "鱼肉": ("鱼",),
        "猪肉": ("猪", "培根", "火腿", "烟肉"),
    }.items():
        if any(word in joined for word in terms):
            tags.append(tag)
    return tags


def compose(detail, request, nutrition):
    item = {"productCode": detail["code"], "quantity": 1}
    names, components, rounds = [], [], []
    if detail.get("rounds"):
        for round_ in detail["rounds"]:
            # Bounded MVP handles one choice per mandatory round. Never invent a valid basket.
            if round_.get("quantity") != 1 or round_.get("minQuantity") != 1:
                raise ValueError("复杂套餐轮次需Agent配方处理")
            choices = [c for c in round_["choices"] if c.get("maxQuantity", -1) != 0]
            choices = [
                c for c in choices if not set(tags_for([c["name"]])).intersection(request.avoid)
            ]
            if not choices:
                raise ValueError("套餐没有符合排除偏好的选项")

            def rank(choice):
                kcal = nutrition.get(normalize(choice["name"]))
                preferred = len(set(tags_for([choice["name"]])).intersection(request.prefer))
                return (
                    -preferred,
                    request.max_kcal is not None and kcal is None,
                    not any(
                        t in choice["name"]
                        for t in ("汉堡", "鸡腿堡", "麦香鸡", "麦香鱼", "麦满分")
                    ),
                    -int(choice.get("isDefault", 0)),
                    kcal if kcal is not None else 10000,
                    choice["code"],
                )

            choice = min(choices, key=rank)
            selected = {"code": choice["code"], "quantity": 1}
            mod = modification(choice)
            if mod:
                selected["modification"] = mod
            rounds.append({"round": str(round_["id"]), "comboItemList": [selected]})
            names.append(choice["name"] + ("【可特调】" if choice.get("supportModify") else ""))
            components.append(choice["name"])
        item["roundList"] = rounds
    else:
        mod = modification(detail)
        if mod:
            item["modification"] = mod
        components.append(detail["name"])
    kcal_values = [nutrition.get(normalize(n)) for n in components]
    kcal = sum(kcal_values) if all(v is not None for v in kcal_values) else None
    label = detail["name"] + ("【可特调】" if detail.get("supportModify") else "")
    if names:
        label += "（" + " + ".join(names) + "）"
    return item, label, kcal, tags_for(components)


def listed_price(meal):
    try:
        value = Decimal(str(meal.get("currentPrice", "NaN")))
        return float(value) if value.is_finite() and value >= 0 else float("inf")
    except InvalidOperation:
        return float("inf")


def coupon_window(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*-\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", value
    )
    if not match:
        return None
    try:
        start, end = [
            datetime.strptime(part, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Shanghai"))
            for part in match.groups()
        ]
    except ValueError:
        return None
    return (start, end) if start < end else None


def quote_price(quote, items):
    price = quote.get("price")
    if type(price) is not int or price < 0:
        raise McpFailure("business", "官方应付price不是非负整数分")
    expected = Counter()
    actual = Counter()
    for item in items:
        expected[item["productCode"]] += item["quantity"]
    for row in quote.get("productList", []):
        if type(row.get("quantity")) is not int:
            raise McpFailure("business", "试算返回商品数量不明")
        actual[row["productCode"]] += row["quantity"]
    if not actual or actual != expected:
        raise McpFailure("business", "试算购物篮为空或与请求的商品和数量不一致")
    return price


async def automatic(
    request: Request,
    gateway,
    *,
    city: str,
    keyword: str,
    walks: list[int],
    wait: int | None,
    store_limit=2,
):
    if not 1 <= store_limit <= 2 or len(walks) not in (0, store_limit):
        raise ValueError("自动模式最多2店；步行分钟列表须与门店数量一致，或留空不作时间判断")
    if any(not 0 <= n <= 240 for n in walks) or (wait is not None and not 0 <= wait <= 180):
        raise ValueError("步行或出餐假设超出支持范围")
    nearby = success(
        await gateway.call(
            "query-nearby-stores", {"city": city, "keyword": keyword, "searchType": 2, "beType": 1}
        )
    )
    selected_stores = [s for s in nearby if s.get("businessStatus") is True][:store_limit]
    nutrition = nutrition_table(success(await gateway.call("list-nutrition-foods", {})))
    # Personal and store applicability are distinct. Never claim possession implies applicability.
    personal = success(await gateway.call("query-my-coupons", {"page": "1", "pageSize": "200"}))
    owned = {c["id"] for c in personal.get("coupons", []) if c.get("enable") == 1}
    success(
        await gateway.call("campaign-calendar", {"specifiedDate": request.start.date().isoformat()})
    )
    stores, offers, warnings = [], [], []
    for index, raw_store in enumerate(selected_stores):
        code = raw_store["storeCode"]
        base = {"storeCode": code, "orderType": 1, "beType": 1}
        stores.append(
            Store(
                id=code,
                name=raw_store["storeName"],
                walk_minutes=walks[index] if walks else None,
                walk_basis="调用者明确输入的单程步行假设；非实时路线",
                wait_minutes=wait,
                wait_basis="调用者明确输入的排队与出餐假设；非实时队列",
            )
        )
        menu = success(await gateway.call("query-meals", base))
        coupons = success(await gateway.call("query-store-coupons", base))
        applicable = {}
        for coupon in coupons:
            if coupon.get("couponId") not in owned:
                continue
            valid_window = coupon_window(coupon.get("tradeDateTime"))
            arrival = max(request.start, datetime.now(timezone.utc)) + timedelta(
                minutes=walks[index] if walks else 0
            )
            if valid_window is None or not valid_window[0] <= arrival < valid_window[1]:
                warnings.append("部分券无法核实到店时有效性，未作为含券候选。")
                continue
            for product in coupon.get("products", []):
                applicable.setdefault(product["productCode"], coupon)
        meals = dict(menu.get("meals", {}))
        for product_code, coupon in applicable.items():
            product = next(p for p in coupon["products"] if p["productCode"] == product_code)
            meals.setdefault(product_code, {"name": product["productName"]})
        # Candidate heuristics choose main-meal baskets, not merchandise or a cheap sauce.
        pool = [
            (c, m)
            for c, m in meals.items()
            if any(t in m["name"] for t in ("套餐", "随心配", "汉堡", "鸡腿堡", "两件套", "三件套"))
            and not any(t in m["name"] for t in ("双人", "分享", "七件", "周边"))
        ]
        pool.sort(
            key=lambda pair: (
                pair[0] not in applicable,
                (
                    request.max_kcal is not None
                    and nutrition.get(normalize(pair[1]["name"])) is None
                    and not any(t in pair[1]["name"] for t in ("随心配", "套餐"))
                ),
                -len(set(tags_for([pair[1]["name"]])).intersection(request.prefer)),
                listed_price(pair[1]),
                pair[0],
            )
        )
        # Preserve distinct candidate roles: an existing coupon, a low-price bundle,
        # and a preference-ranked main meal. All final prices still require a quote.
        candidates = []

        def add(pair):
            if pair and pair[0] not in {p[0] for p in candidates} and len(candidates) < 3:
                candidates.append(pair)

        add(next((p for p in pool if p[0] in applicable), None))
        bundles = [p for p in pool if any(t in p[1]["name"] for t in ("随心配", "套餐"))]
        add(min(bundles, key=lambda p: (listed_price(p[1]), p[0])) if bundles else None)
        for pair in pool:
            add(pair)
        # Maximum three full candidates per store; never Cartesian enumeration.
        for product_code, meal in candidates:
            try:
                detail = success(
                    await gateway.call("query-meal-detail", base | {"code": product_code})
                )
                if detail.get("code") != product_code:
                    raise ValueError("详情餐品编码不匹配")
                item, label, kcal, tags = compose(detail, request, nutrition)
                coupon = applicable.get(product_code)
                args = base | {"items": [item], "needTableware": False}
                if coupon:
                    item.update(couponId=coupon["couponId"], couponCode=coupon["couponCode"])
                quote = success(await gateway.call("calculate-price", args))
                price = quote_price(quote, [item])
                stamp = datetime.now(timezone.utc)
                # Comparison changes ONLY the coupon parameters of the exact same basket.
                baseline = None
                if coupon:
                    original_item = {
                        k: v for k, v in item.items() if k not in {"couponId", "couponCode"}
                    }
                    try:
                        baseline_quote = success(
                            await gateway.call(
                                "calculate-price",
                                base | {"items": [original_item], "needTableware": False},
                            )
                        )
                        baseline = quote_price(baseline_quote, [original_item])
                        if baseline < price:
                            baseline = None
                    except McpFailure as exc:
                        if exc.code != "business":
                            raise
                        warnings.append("部分无券对照为空购物篮或不可购买，未计算节省金额。")
                offers.append(
                    Offer(
                        id=f"{code}-{product_code}",
                        store_id=code,
                        name=label,
                        payable_cents=price,
                        baseline_cents=baseline,
                        kcal=kcal,
                        tags=tags,
                        coupon="已有且本店核价通过的券" if coupon else None,
                        quote_at=stamp,
                        expires_at=coupon_window(coupon["tradeDateTime"])[1] if coupon else None,
                        evidence="本轮官方calculate-price.data.price（整数分）",
                    )
                )
            except ValueError:
                warnings.append(
                    "部分复杂套餐/未知营养结构未纳入本轮比较，可通过Agent配方单独处理。"
                )
            except McpFailure as exc:
                if exc.code != "business":
                    raise
                warnings.append("部分候选业务失败或券不适用，已排除；未当作免费餐。")
    return Snapshot(
        mode="live",
        stores=stores,
        offers=offers,
        warnings=list(dict.fromkeys(warnings))
        + [
            "自动适配每店最多3个候选，菜单价只用于候选筛选，报告金额来自整单试算。",
            "营养仅精确餐名匹配，整餐任一项未知则总热量未知；偏好标签不是过敏原保证。",
            "步行与出餐时间是调用者假设；未接入地图或实时排队。价格不锁定，未来用餐需临近出发重试。",
        ],
    )
