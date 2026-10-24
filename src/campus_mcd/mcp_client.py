"""Official SDK transport. Fail closed to an eight-tool read-only allowlist."""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
from jsonschema import Draft202012Validator
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .config import Config

READ_ONLY = frozenset(
    {
        "query-nearby-stores",
        "query-meals",
        "query-meal-detail",
        "list-nutrition-foods",
        "query-my-coupons",
        "query-store-coupons",
        "calculate-price",
        "campaign-calendar",
    }
)


class McpFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def classify(exc: BaseException) -> McpFailure:
    if isinstance(exc, BaseExceptionGroup):
        errors = [classify(e) for e in exc.exceptions]
        return next((e for e in errors if e.code != "network"), errors[0])
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 401:
            return McpFailure("401", "MCP认证失败，请在本地更新Token")
        if code == 429:
            return McpFailure("429", "MCP限流，请稍后重试；本次不自动重放请求")
        if code == 403:
            return McpFailure("403", "MCP拒绝访问，请检查授权与网络环境")
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return McpFailure("timeout", "MCP请求超时，本轮报价无效，请重新查询")
    if isinstance(exc, McpFailure):
        return exc
    return McpFailure("network", "MCP连接或协议异常，请检查网络后重试")


def unpack(result):
    if result.isError:
        raise McpFailure("tool", "MCP工具返回错误；可能售罄、券失效或参数不适用，请重新查询")
    if result.structuredContent is not None:
        return result.structuredContent
    texts = [c.text for c in result.content if c.type == "text"]
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except (ValueError, TypeError):
            pass
    return {"text": texts}


class Gateway:
    def __init__(self, session, tools, timeout=25):
        self.session, self.tools, self.timeout = session, tools, timeout
        self.calls = 0
        self.quotes = 0
        self.audit = []

    def validate(self, name: str, arguments: dict):
        if name not in READ_ONLY:
            raise McpFailure("blocked", "本项目只允许8个查询及试算工具，禁止账户与订单变更")
        if name not in self.tools:
            raise McpFailure("missing_tool", f"当前服务未发现工具 {name}")
        schema = self.tools[name]["inputSchema"]

        # Local refs work; reject remote refs instead of fetching arbitrary URLs.
        def remote_ref(node):
            if isinstance(node, dict):
                return any(
                    k == "$ref" and not str(v).startswith("#") or remote_ref(v)
                    for k, v in node.items()
                )
            return isinstance(node, list) and any(remote_ref(v) for v in node)

        if remote_ref(schema):
            raise McpFailure("schema", "发现远程schema引用，需人工检查，未执行调用")
        validator = Draft202012Validator(schema)
        if next(validator.iter_errors(arguments), None):
            raise McpFailure("arguments", "参数不符合实时发现的inputSchema，请检查本地工具描述")

    async def call(self, name: str, arguments: dict):
        if name not in READ_ONLY:
            raise McpFailure("blocked", "本项目只允许8个查询及试算工具，禁止账户与订单变更")
        if name not in self.tools:
            raise McpFailure("missing_tool", f"当前服务未发现工具 {name}")
        self.validate(name, arguments)
        if self.calls >= 32 or (name == "calculate-price" and self.quotes >= 12):
            raise McpFailure("limit", "已达到单轮32次调用或12次报价的上限")
        self.calls += 1
        self.quotes += name == "calculate-price"
        try:
            result = await asyncio.wait_for(self.session.call_tool(name, arguments), self.timeout)
            value = unpack(result)
            self.audit.append(
                {
                    "tool": name,
                    "arguments": arguments,
                    "result": value,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if name == "calculate-price" and isinstance(value, dict):
                data = value.get("data")
                if isinstance(data, dict) and data.get("productList") == []:
                    raise McpFailure("business", "整单试算返回空购物篮，不能当成免费餐或有效对照")
            return value
        except Exception as exc:
            raise classify(exc) from None


@asynccontextmanager
async def connect(config: Config):
    try:
        async with (
            httpx.AsyncClient(
                headers={"Authorization": f"Bearer {config.token}"},
                timeout=httpx.Timeout(config.timeout),
                follow_redirects=False,
            ) as http_client,
            streamable_http_client(config.url, http_client=http_client) as (read, write, _),
        ):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=config.timeout)
            ) as session:
                await asyncio.wait_for(session.initialize(), config.timeout)
                tools, cursor = {}, None
                for _ in range(10):
                    page = await asyncio.wait_for(session.list_tools(cursor=cursor), config.timeout)
                    tools.update(
                        {t.name: t.model_dump(by_alias=True, exclude_none=True) for t in page.tools}
                    )
                    cursor = page.nextCursor
                    if not cursor:
                        break
                else:
                    raise McpFailure("limit", "工具分页超过上限")
                yield Gateway(session, tools, config.timeout)
    except (ValueError, KeyError, TypeError, IndexError):
        raise
    except Exception as exc:
        raise classify(exc) from None
