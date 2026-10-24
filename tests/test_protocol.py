"""Real SDK over local HTTP; proves protocol plumbing, not official service acceptance."""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from campus_mcd.live import LiveRecipe, execute
from campus_mcd.mcp_client import connect


@pytest.fixture(scope="module")
def local_server():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    child = subprocess.Popen(
        [sys.executable, "tests/fake_mcp_server.py", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            if child.poll() is not None:
                pytest.fail("Local MCP test server failed to start")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            pytest.fail("Local MCP test server start timeout")
        yield SimpleNamespace(
            url=f"http://127.0.0.1:{port}/mcp", token="local-test-only", timeout=5
        )
    finally:
        child.terminate()
        child.wait(timeout=5)


async def test_streamable_http_discovery_and_quote(local_server):
    async with connect(local_server) as gateway:
        schema = gateway.tools["calculate-price"]["inputSchema"]
        assert "store" in schema["required"]
        result = await gateway.call("calculate-price", {"store": "s1", "meal": "m1"})
        assert result["total"] == "18.80"
        assert gateway.calls == 1


async def test_full_recipe_over_real_local_protocol(local_server):
    recipe = LiveRecipe.model_validate(
        json.loads(Path("examples/live-recipe.test-double.json").read_text(encoding="utf-8"))
    )
    async with connect(local_server) as gateway:
        result = await execute(recipe, gateway)
        assert result.offers[0].payable_cents == 1880
        assert gateway.calls == 3 and gateway.quotes == 1
        assert len(gateway.audit) == 3
