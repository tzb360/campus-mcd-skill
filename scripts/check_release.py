#!/usr/bin/env python3
"""Check tracked release files without ever printing a credential value."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "README.md",
    "SKILL.md",
    "CONTEST_DECLARATION.md",
    "MCP_INTEGRATION.md",
    "mcp-config.example.json",
    "LICENSE",
    "pyproject.toml",
    ".gitignore",
}
DECLARATION_SHA256 = "cd28101bcb29cc8fb24b372fe91ce6b42c4a1487a54e01f7ade0c8c6a84241b7"


def main():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    tracked = [name for name in tracked if name]
    if not REQUIRED <= set(tracked):
        raise ValueError("Required entry files must be tracked before release")
    tokens = []
    token_file = ROOT / "private" / "mcd-token.txt"
    if token_file.is_file():
        tokens.append(token_file.read_bytes().strip())
    if os.environ.get("MCD_MCP_TOKEN"):
        tokens.append(os.environ["MCD_MCP_TOKEN"].encode())
    tokens = [token for token in tokens if len(token) >= 8 and not token.startswith(b"${")]
    for name in tracked:
        if (
            any(part in {"private", ".venv", "output", ".git"} for part in Path(name).parts)
            or ".private." in name
        ):
            raise ValueError("Private file appears in tracked release")
        data = (ROOT / name).read_bytes()
        if any(token in data for token in tokens):
            raise ValueError("A real credential appears in tracked release; value suppressed")
    config = json.loads((ROOT / "mcp-config.example.json").read_text(encoding="utf-8"))
    if config["mcpServers"]["mcd-mcp"]["headers"]["Authorization"] != "Bearer ${MCD_MCP_TOKEN}":
        raise ValueError("Example configuration must use the environment placeholder")
    if (
        hashlib.sha256((ROOT / "CONTEST_DECLARATION.md").read_bytes()).hexdigest()
        != DECLARATION_SHA256
    ):
        raise ValueError(
            "Official declaration changed; compare directly with the official repository"
        )
    for name in ("live-example.html", "demo-data.js", "index.html"):
        content = (ROOT / "docs" / name).read_text(encoding="utf-8")
        if any(
            forbidden in content
            for forbidden in ("couponId", "couponCode", "storeCode", "traceId", "Authorization")
        ):
            raise ValueError("Raw member/store fields appear in public demo")
    print(
        f"Release check passed: {len(tracked)} tracked files; required files, declaration, placeholders, public demo fields and configured-token exclusion checked."
    )


if __name__ == "__main__":
    main()
