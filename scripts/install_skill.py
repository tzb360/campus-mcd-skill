#!/usr/bin/env python3
"""Copy a self-contained skill. Refuse overwriting an existing installation."""

import argparse
import shutil
import sys
from pathlib import Path


def install(destination: Path):
    source = Path(__file__).resolve().parents[1]
    if destination.exists():
        raise FileExistsError("目标已存在；请先人工备份，安装器不会覆盖")
    ignore = shutil.ignore_patterns(
        ".git",
        ".venv",
        "__pycache__",
        "*.egg-info",
        ".pytest_cache",
        ".ruff_cache",
        "private",
        "output",
        "dist",
        "build",
        ".env",
        ".env.*",
        "*.private.*",
        ".DS_Store",
    )
    shutil.copytree(source, destination, ignore=ignore)
    print(f"Skill已复制到 {destination}；请在所选Python环境执行 pip install '{destination}'")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--dest", type=Path, default=Path.home() / ".codex" / "skills" / "campus-mcd")
    install(p.parse_args().dest)
