import html
from importlib.resources import files


def public_view(result: dict, private_details=False):
    options = []
    for option in result["options"]:
        item = dict(option)
        if item["choice"]:
            c = item["choice"]
            keep = {
                "meal",
                "payable_cents",
                "savings_cents",
                "kcal",
                "minutes",
                "slack_minutes",
                "walk_minutes",
                "wait_minutes",
                "eat_minutes",
                "buffer_minutes",
                "risk",
            }
            if private_details:
                keep |= {"store", "depart_at", "leave_store_by", "return_at", "quote_at"}
            item["choice"] = {k: v for k, v in c.items() if k in keep}
            item["choice"]["coupon"] = "含券试算" if c["coupon"] else "无券试算"
        options.append(item)
    return {
        "mode": result["mode"],
        "window_minutes": result["window_minutes"],
        "budget_cents": result["budget_cents"],
        "title": result["title"],
        "options": options,
        "time_window": result["time_window"] if private_details else "时段已隐藏",
        "candidate_count": result["candidate_count"],
    }


def render(result: dict, private_details=False) -> str:
    value = public_view(result, private_details)

    def e(v):
        return html.escape(str(v), quote=True)

    label = "模拟数据 · 非真实菜单/报价" if value["mode"] == "mock" else "MCP本轮试算 · 不锁价"
    cards = []
    for option in value["options"]:
        c = option["choice"]
        if not c:
            cards.append(
                f"<article><span>{e(option['key'])} / {e(option['label'])}</span><h2>这次，先别赶。</h2><p>{e(option['reason'])}</p></article>"
            )
            continue
        saved = (
            "无同单对照，不展示节省金额"
            if c["savings_cents"] is None
            else f"同单优惠对照节省 ¥{c['savings_cents'] / 100:.2f}"
        )
        detail = (
            f"<p>{e(c.get('store', ''))}<br>出发 {e(c.get('depart_at', ''))}<br>离店 {e(c.get('leave_store_by', ''))}<br>返课 {e(c.get('return_at', ''))}</p>"
            if private_details
            else ""
        )
        nutrition = "热量未知" if c["kcal"] is None else f"{c['kcal']:g} 千卡"
        if c["kcal"] is not None and value["mode"] == "mock":
            nutrition += "（整餐模拟值）"
        cards.append(f"""<article><span>{e(option["key"])} / {e(option["label"])}</span>
        <h2>{e(c["meal"])}</h2><div class="price">¥{c["payable_cents"] / 100:.2f}</div>
        <p>{e(saved)} · {e(c["coupon"])}</p><p>{e(nutrition)}</p><div class="route"><b>往返步行 {2 * c["walk_minutes"]}′</b><b>出餐假设 {c["wait_minutes"]}′</b><b>用餐 {c["eat_minutes"]}′ + 缓冲 {c["buffer_minutes"]}′</b><b>返课余量 {c["slack_minutes"]}′</b></div>
        <p>{e(option["reason"])}</p><p>{e(c["risk"])}</p>{detail}</article>""")
    template = files("campus_mcd").joinpath("data/report.html").read_text(encoding="utf-8")
    css = files("campus_mcd").joinpath("data/style.css").read_text(encoding="utf-8")
    return (
        template.replace("{{style}}", css)
        .replace("{{label}}", e(label))
        .replace("{{window}}", str(value["window_minutes"]))
        .replace("{{budget}}", f"{value['budget_cents'] / 100:.2f}")
        .replace("{{title}}", e(value["title"]))
        .replace("{{cards}}", "".join(cards))
        .replace("{{time}}", e(value["time_window"]))
    )
