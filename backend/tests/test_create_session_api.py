"""POST /api/sessions — dashboard-only session creation."""

import re

from fastapi.testclient import TestClient

import store as store_module
from api.main import app
from store import session_exists

client = TestClient(app)
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def test_post_create_session(tmp_path, monkeypatch):
    monkeypatch.setattr(store_module, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DATA_DIR", tmp_path)

    res = client.post("/api/sessions")
    assert res.status_code == 200
    body = res.json()
    assert UUID_RE.match(body["session_id"])
    assert body["view_url"].endswith(f"/s/{body['session_id']}")
    assert session_exists(body["session_id"])

    get_res = client.get(f"/api/sessions/{body['session_id']}")
    assert get_res.status_code == 200
