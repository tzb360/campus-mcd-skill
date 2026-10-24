"""LOCAL TEST DOUBLE. Its argument and response fields are NOT McD's schema."""

import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "CampusMcD test double", host="127.0.0.1", port=int(sys.argv[1]), log_level="CRITICAL"
)


@mcp.tool(name="calculate-price")
def price(store: str, meal: str) -> dict:
    """Fictional local quote, not an official McD response."""
    return {"ok": True, "total": "18.80", "store": store, "meal": meal}


@mcp.tool(name="query-nearby-stores")
def stores() -> dict:
    return {"ok": True, "id": "s1", "name": "Local fictional store"}


@mcp.tool(name="query-meal-detail")
def detail() -> dict:
    return {"ok": True, "id": "m1", "name": "Local fictional meal"}


mcp.run(transport="streamable-http")
