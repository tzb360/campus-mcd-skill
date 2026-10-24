#!/usr/bin/env python3
"""Build a static interactive demo using the SAME Python planner for every state."""

import json
from datetime import timedelta
from importlib.resources import files
from pathlib import Path

from campus_mcd.models import Request, Snapshot
from campus_mcd.planner import plan
from campus_mcd.report import render

root = Path(__file__).resolve().parents[1]
data = json.loads(files("campus_mcd").joinpath("data/mock.json").read_text())
snapshot = Snapshot.model_validate(data["snapshot"])
scenarios = {}
for budget in (10, 15, 20, 25, 30):
    for minutes in (25, 40, 60, 90):
        for chicken in (0, 1):
            request = Request.model_validate(data["requests"]["lunch"])
            request.budget_cents = budget * 100
            request.deadline = request.start + timedelta(minutes=minutes)
            if chicken:
                request.prefer = ["鸡肉"]
                request.avoid = ["牛肉"]
                request.max_kcal = 700
            result = plan(request, snapshot)
            content = render(result)
            body = content[content.index("<main>") : content.index("</main>") + 7]
            scenarios[f"{budget}-{minutes}-{chicken}"] = body
(root / "docs/demo-data.js").write_text(
    "// 40 precomputed mock states from the Python planner; NOT live data.\nwindow.CAMPUS_DEMO = "
    + json.dumps(scenarios, ensure_ascii=False)
    + ";\n",
    encoding="utf-8",
)
(root / "docs/style.css").write_text(
    files("campus_mcd").joinpath("data/style.css").read_text(), encoding="utf-8"
)
(root / "docs/example-report.html").write_text(
    render(plan(Request.model_validate(data["requests"]["chicken"]), snapshot)), encoding="utf-8"
)
print(f"Built {len(scenarios)} simulated states; no account data used")
