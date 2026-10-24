import json
import subprocess
import sys
from pathlib import Path


def test_cli_from_other_working_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    run = Path("scripts/run.py").resolve()
    result = subprocess.run(
        [sys.executable, str(run), "demo", "--scenario", "rush"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["mode"] == "mock"
    assert (
        json.loads((tmp_path / "output/plan.json").read_text(encoding="utf-8"))["candidate_count"]
        == 0
    )


def test_install_isolated_and_non_overwriting(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    destination = tmp_path / "campus-mcd"
    install = Path("scripts/install_skill.py")
    result = subprocess.run(
        [sys.executable, str(install), "--dest", str(destination)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert (destination / "SKILL.md").exists()
    assert not any((destination / name).exists() for name in (".venv", ".git", "private", "output"))
    again = subprocess.run(
        [sys.executable, str(install), "--dest", str(destination)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert again.returncode != 0
    assert (destination / "SKILL.md").exists()
