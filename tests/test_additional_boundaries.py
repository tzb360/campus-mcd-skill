from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from campus_mcd.config import Config
from campus_mcd.live import cents
from campus_mcd.mcp_client import McpFailure
from campus_mcd.planner import plan


def test_quote_expires_before_arrival(request_value, snapshot):
    for offer in snapshot.offers:
        offer.expires_at = request_value.start + timedelta(minutes=1)
    assert plan(request_value, snapshot)["candidate_count"] == 0


def test_no_time_if_roundtrip_returns_after_deadline(request_value, snapshot):
    request_value.deadline = request_value.start + timedelta(minutes=33)
    assert plan(request_value, snapshot)["candidate_count"] == 0


def test_invalid_numeric_quote_is_handled():
    with pytest.raises(ValueError):
        cents("sold out", "yuan")


def test_token_file_privacy(tmp_path, monkeypatch):
    file = tmp_path / "token.txt"
    file.write_text("local-test-only")
    monkeypatch.delenv("MCD_MCP_TOKEN", raising=False)
    monkeypatch.setenv("CAMPUS_MCD_TOKEN_FILE", str(file))
    file.chmod(0o600)
    assert Config.from_env().token == "local-test-only"
    import os

    if os.name != "nt":
        file.chmod(0o644)
        with pytest.raises(ValueError):
            Config.from_env()


async def test_gateway_total_query_limit():
    from mcp.types import CallToolResult

    from campus_mcd.mcp_client import Gateway

    session = AsyncMock()
    session.call_tool.return_value = CallToolResult(content=[], structuredContent={"ok": True})
    gateway = Gateway(session, {"query-meals": {"inputSchema": {"type": "object"}}})
    for _ in range(32):
        await gateway.call("query-meals", {})
    with pytest.raises(McpFailure) as error:
        await gateway.call("query-meals", {})
    assert error.value.code == "limit"
    assert session.call_tool.await_count == 32
