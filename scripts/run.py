#!/usr/bin/env python3
"""Run an installed skill without depending on the shell's working directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from campus_mcd.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
