import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date
from importlib.resources import files
from pathlib import Path

from .calendar import free_windows
from .config import Config
from .live import LiveRecipe, execute
from .mcp_client import McpFailure, connect
from .models import Request, Snapshot
from .official import automatic
from .planner import plan
from .report import render


def read(path):
    value = Path(path)
    if value.stat().st_size > 2_000_000:
        raise ValueError("输入JSON超过2MB")
    return json.loads(value.read_text(encoding="utf-8"))


def write(path, data, private=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement avoids following a pre-existing destination symlink.
    import tempfile

    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data)
        os.chmod(temp, 0o600 if private else 0o644)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def dumps(value):
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


async def online(args):
    async with connect(Config.from_env()) as gateway:
        if args.command == "discover":
            write(args.output, dumps({"tools": gateway.tools}))
            return {
                "saved": args.output,
                "discovered": len(gateway.tools),
                "live_planning_verified": False,
            }
        if args.command == "call":
            data = await gateway.call(args.tool, read(args.arguments))
            write(args.output, dumps(data))
            return {"saved_private_result": args.output, "tool": args.tool}
        request = Request.model_validate(read(args.request))
        if args.command == "live-auto":
            snapshot = await automatic(
                request,
                gateway,
                city=args.city,
                keyword=args.keyword,
                walks=args.walk_minutes,
                wait=args.wait_minutes,
                store_limit=args.store_limit,
            )
        else:
            recipe = LiveRecipe.model_validate(read(args.recipe))
            snapshot = await execute(recipe, gateway)
        write(args.audit, dumps(gateway.audit))
        result = plan(request, snapshot)
        write(args.output, dumps(result))
        if args.report:
            write(args.report, render(result, args.private_details), private=args.private_details)
        return {
            "saved_private_plan": args.output,
            "calls": gateway.calls,
            "quotes": gateway.quotes,
            "feasible_candidates": result["candidate_count"],
        }


def parser():
    p = argparse.ArgumentParser(description="下课开麦：预算、餐品与返课时间一起算")
    sub = p.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="零账户离线完整演示")
    demo.add_argument("--request", help="自定义结构化需求JSON")
    demo.add_argument("--scenario", choices=["lunch", "rush", "chicken"], default="lunch")
    demo.add_argument("--report", default="output/survival.html")
    demo.add_argument("--output", default="output/plan.json")
    demo.add_argument("--private-details", action="store_true")
    d = sub.add_parser("discover", help="真实MCP初始化与tools/list")
    d.add_argument("--output", default="private/tools.json")
    c = sub.add_parser("call", help="按发现的schema执行只读工具")
    c.add_argument("--tool", required=True)
    c.add_argument("--arguments", required=True)
    c.add_argument("--output", default="private/result.json")
    live = sub.add_parser("live", help="执行Agent按本轮schema制作的调用配方并重新核价")
    live.add_argument("--recipe", required=True)
    live.add_argument("--request", required=True)
    live.add_argument("--output", default="private/plan.json")
    live.add_argument("--audit", default="private/audit.json")
    live.add_argument("--report", default="private/survival.html")
    live.add_argument("--private-details", action="store_true")
    auto = sub.add_parser(
        "live-auto", help="已按真实schema实现的到店自取自动适配，缺少耗时不判可行"
    )
    auto.add_argument("--request", required=True)
    auto.add_argument("--city", required=True)
    auto.add_argument("--keyword", required=True)
    auto.add_argument("--walk-minutes", type=int, nargs="*", default=[])
    auto.add_argument("--wait-minutes", type=int)
    auto.add_argument("--store-limit", type=int, choices=[1, 2], default=2)
    auto.add_argument("--output", default="private/auto-plan.json")
    auto.add_argument("--audit", default="private/auto-audit.json")
    auto.add_argument("--report", default="private/auto-survival.html")
    auto.add_argument("--private-details", action="store_true")
    cal = sub.add_parser("ics", help="读取已展开的单次ICS课表，不上传文件")
    cal.add_argument("file")
    cal.add_argument("--date", required=True)
    cal.add_argument("--zone", default="Asia/Shanghai")
    return p


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args()
    # SDK/httpx error logs can contain service-provided strings; use safe CLI messages only.
    logging.getLogger().setLevel(logging.CRITICAL)
    try:
        if args.command == "demo":
            data = json.loads(
                files("campus_mcd").joinpath("data/mock.json").read_text(encoding="utf-8")
            )
            request = read(args.request) if args.request else data["requests"][args.scenario]
            result = plan(
                Request.model_validate(request), Snapshot.model_validate(data["snapshot"])
            )
            write(args.output, dumps(result))
            write(args.report, render(result, args.private_details), private=args.private_details)
            print(
                dumps(
                    {
                        "mode": "mock",
                        "feasible_candidates": result["candidate_count"],
                        "plan": args.output,
                        "report": args.report,
                    }
                )
            )
        elif args.command == "ics":
            value = Path(args.file)
            if value.stat().st_size > 1_000_000:
                raise ValueError("ICS超过1MB")
            print(dumps(free_windows(value.read_bytes(), date.fromisoformat(args.date), args.zone)))
        else:
            print(dumps(asyncio.run(online(args))))
    except McpFailure as exc:
        print(dumps({"error": exc.code, "message": str(exc)}), file=sys.stderr)
        return 2
    except (ValueError, KeyError, TypeError, IndexError, OSError):
        # Pydantic validation errors echo input values: don't print raw errors/private paths.
        print(
            dumps(
                {
                    "error": "input",
                    "message": "配置或输入无效；检查必填字段、含时区时间、金额整数分和来源映射。详见docs/input.md。",
                }
            ),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
