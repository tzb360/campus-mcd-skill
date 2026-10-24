from unittest.mock import AsyncMock

import httpx
import pytest
from mcp.types import CallToolResult, TextContent

from campus_mcd.config import Config
from campus_mcd.mcp_client import Gateway, McpFailure, classify


@pytest.fixture
def gateway():
    session = AsyncMock()
    session.call_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text='{"pay":19.9}')]
    )
    tools = {
        "calculate-price": {
            "inputSchema": {
                "type": "object",
                "properties": {"basket": {"type": "string"}},
                "required": ["basket"],
                "additionalProperties": False,
            }
        }
    }
    return Gateway(session, tools, timeout=0.05)


async def test_discovered_schema_and_actual_tool_result(gateway):
    assert await gateway.call("calculate-price", {"basket": "test"}) == {"pay": 19.9}
    gateway.session.call_tool.assert_awaited_once_with("calculate-price", {"basket": "test"})


@pytest.mark.parametrize(
    "tool",
    [
        "create-order",
        "auto-bind-coupons",
        "mall-create-order",
        "draw-lottery",
        "delivery-create-address",
    ],
)
async def test_account_mutations_blocked(gateway, tool):
    with pytest.raises(McpFailure, match="禁止"):
        await gateway.call(tool, {})
    gateway.session.call_tool.assert_not_called()


async def test_bad_arguments_blocked_before_network(gateway):
    with pytest.raises(McpFailure) as error:
        await gateway.call("calculate-price", {"invented_param": 1})
    assert error.value.code == "arguments"
    gateway.session.call_tool.assert_not_called()


async def test_missing_tool(gateway):
    with pytest.raises(McpFailure) as error:
        await gateway.call("query-meals", {})
    assert error.value.code == "missing_tool"


async def test_bounded_quotes(gateway):
    for _ in range(12):
        await gateway.call("calculate-price", {"basket": "test"})
    with pytest.raises(McpFailure) as error:
        await gateway.call("calculate-price", {"basket": "test"})
    assert error.value.code == "limit"
    assert gateway.session.call_tool.await_count == 12


@pytest.mark.parametrize(
    "status,code", [(401, "401"), (429, "429"), (403, "403"), (503, "network")]
)
async def test_http_errors_do_not_leak_tokens(gateway, status, code):
    response = httpx.Response(status, request=httpx.Request("POST", "https://mcp.mcd.cn"))
    gateway.session.call_tool.side_effect = httpx.HTTPStatusError(
        "secret-token-value", request=response.request, response=response
    )
    with pytest.raises(McpFailure) as error:
        await gateway.call("calculate-price", {"basket": "test"})
    assert error.value.code == code
    assert "secret-token-value" not in str(error.value)


@pytest.mark.parametrize(
    "exc,code", [(TimeoutError(), "timeout"), (httpx.ConnectError("secret"), "network")]
)
async def test_timeout_disconnect(gateway, exc, code):
    gateway.session.call_tool.side_effect = exc
    with pytest.raises(McpFailure) as error:
        await gateway.call("calculate-price", {"basket": "test"})
    assert error.value.code == code


async def test_tool_business_error(gateway):
    gateway.session.call_tool.return_value = CallToolResult(isError=True, content=[])
    with pytest.raises(McpFailure) as error:
        await gateway.call("calculate-price", {"basket": "test"})
    assert error.value.code == "tool"


def test_exception_group_status():
    assert classify(ExceptionGroup("SDK", [TimeoutError()])).code == "timeout"


def test_token_missing_and_repr_safe(monkeypatch):
    monkeypatch.delenv("MCD_MCP_TOKEN", raising=False)
    with pytest.raises(ValueError):
        Config.from_env()
    assert "secret" not in repr(Config(token="secret"))


async def test_remote_schema_refs_not_fetched(gateway):
    gateway.tools["calculate-price"]["inputSchema"] = {"$ref": "https://invalid.invalid/schema"}
    with pytest.raises(McpFailure) as error:
        await gateway.call("calculate-price", {})
    assert error.value.code == "schema"
    gateway.session.call_tool.assert_not_called()
