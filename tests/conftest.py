import json
from importlib.resources import files

import pytest

from campus_mcd.models import Request, Snapshot


@pytest.fixture
def data():
    return json.loads(files("campus_mcd").joinpath("data/mock.json").read_text())


@pytest.fixture
def request_value(data):
    return Request.model_validate(data["requests"]["lunch"])


@pytest.fixture
def snapshot(data):
    return Snapshot.model_validate(data["snapshot"])


@pytest.fixture(autouse=True)
def isolate_real_credentials(monkeypatch, tmp_path):
    """Tests must never read an owner's configured token or contact their account."""
    monkeypatch.delenv("MCD_MCP_TOKEN", raising=False)
    monkeypatch.setenv("CAMPUS_MCD_TOKEN_FILE", str(tmp_path / "unconfigured-token.txt"))
