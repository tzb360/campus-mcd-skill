"""Bounded comparison of complete quoted baskets, never menu-price arithmetic."""

from datetime import datetime, timedelta, timezone

from .models import Request, Snapshot

POLICIES = (("A", "预算优先"), ("B", "时间优先"), ("C", "均衡推荐"))


def plan(request: Request, snapshot: Snapshot, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    window = int((request.deadline - request.start).total_seconds() // 60)
    window = min(window, request.available_minutes or window)
    # Starting late must not extend the original deadline/available window.
    end = request.start + timedelta(minutes=window)
    start = (
        max(request.start, now.astimezone(request.start.tzinfo))
        if snapshot.mode == "live"
        else request.start
    )
    window = max(0, int((end - start).total_seconds() // 60))
    stores = {s.id: s for s in snapshot.stores}
    candidates, rejected = [], []
    for offer in snapshot.offers:
        store = stores[offer.store_id]
        reason = None
        age = (now - offer.quote_at).total_seconds()
        if not offer.available:
            reason = "售罄或不可售"
        elif offer.expires_at is not None and offer.expires_at <= start + timedelta(
            minutes=store.walk_minutes or 0
        ):
            reason = "优惠券或报价在用餐开始前失效"
        elif snapshot.mode == "live" and not -30 <= age <= 300:
            reason = "报价超出5分钟本地新鲜度策略或时间异常，请重新试算"
        elif offer.payable_cents > request.budget_cents:
            reason = "超过预算"
        elif request.max_kcal and (offer.kcal is None or offer.kcal > request.max_kcal):
            reason = "热量未知或超过上限"
        elif any(tag in offer.tags for tag in request.avoid):
            reason = "与排除偏好冲突"
        elif request.avoid and not offer.tags:
            reason = "缺少偏好核验信息"
        elif store.walk_minutes is None or store.wait_minutes is None:
            reason = "缺少步行或出餐估算，暂不能判断返课可行性"
        elif store.walk_minutes > request.max_walk_minutes:
            reason = "单程步行超过可接受时间"
        if reason:
            rejected.append({"offer": offer.id, "reason": reason})
            continue
        total = (
            2 * store.walk_minutes
            + store.wait_minutes
            + request.eat_minutes
            + request.buffer_minutes
        )
        slack = window - total
        if slack < 0:
            rejected.append({"offer": offer.id, "reason": f"时间不足，还差{-slack}分钟"})
            continue
        preferred = sum(tag in offer.tags for tag in request.prefer)
        # A 0..100 utility scale with explicit money/time/preference weights; no health claims.
        score = round(
            50 * (1 - offer.payable_cents / max(1, request.budget_cents))
            + 30 * slack / max(1, window)
            + 20 * preferred / max(1, len(request.prefer)),
            2,
        )
        savings = None
        if offer.baseline_cents is not None and offer.baseline_cents >= offer.payable_cents:
            savings = offer.baseline_cents - offer.payable_cents
        depart_store = start + timedelta(
            minutes=store.walk_minutes + store.wait_minutes + request.eat_minutes
        )
        candidates.append(
            {
                "offer_id": offer.id,
                "store": store.name,
                "meal": offer.name,
                "payable_cents": offer.payable_cents,
                "savings_cents": savings,
                "kcal": offer.kcal,
                "coupon": offer.coupon,
                "minutes": total,
                "slack_minutes": slack,
                "score": score,
                "preferred": preferred,
                "walk_minutes": store.walk_minutes,
                "wait_minutes": store.wait_minutes,
                "eat_minutes": request.eat_minutes,
                "buffer_minutes": request.buffer_minutes,
                "walk_basis": store.walk_basis,
                "wait_basis": store.wait_basis,
                "depart_at": start.isoformat(),
                "leave_store_by": depart_store.isoformat(),
                "return_at": (depart_store + timedelta(minutes=store.walk_minutes)).isoformat(),
                "quote_at": offer.quote_at.isoformat(),
                "evidence": offer.evidence,
                "risk": "估算条件下可行；排队、路况变化可能消耗余量"
                if slack >= 10
                else "余量不足10分钟，建议缩短行程或重新规划",
            }
        )
    keys = [
        lambda c: (c["payable_cents"], -c["preferred"], c["minutes"], c["offer_id"]),
        lambda c: (c["minutes"], c["payable_cents"], c["offer_id"]),
        lambda c: (-c["score"], c["payable_cents"], c["offer_id"]),
    ]
    options = []
    for (key, label), sort_key in zip(POLICIES, keys):
        best = min(candidates, key=sort_key) if candidates else None
        options.append(
            {
                "key": key,
                "label": label,
                "choice": best,
                "reason": (
                    {
                        "A": "本轮合格候选中应付金额最低",
                        "B": "本轮合格候选中估算总耗时最短",
                        "C": "按省预算50%、返课余量30%、偏好匹配20%评分",
                    }[key]
                    if best
                    else "本轮无满足全部约束的方案，请调整预算、时间或补充估算"
                ),
            }
        )
    title = (
        "课间时间管理者"
        if not candidates
        else ("返课从容派" if max(c["slack_minutes"] for c in candidates) >= 15 else "课间精算师")
    )
    return {
        "mode": snapshot.mode,
        "window_minutes": window,
        "budget_cents": request.budget_cents,
        "title": title,
        "options": options,
        "rejected": rejected,
        "candidate_count": len(candidates),
        "evaluated_count": len(snapshot.offers),
        "warnings": snapshot.warnings
        + [
            "比较范围为本轮最多3店、12份完整候选，非全菜单最优；三种策略可能选择同一方案。",
            "步行按原路往返估算，返课地点不同请单独增加通勤缓冲。",
            "饮食偏好标签不等同于完整配料或过敏原核验。",
        ],
        "time_window": f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}",
        "generated_at": now.isoformat(),
    }
