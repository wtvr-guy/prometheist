from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from prometheist.gui_server import create_app
from prometheist.imprinting import ImprintProfile

ORIGIN = "http://127.0.0.1:8765"


@pytest.fixture
def app(tmp_path, monkeypatch):
    profile = tmp_path / "profile.json"
    profile.write_text(ImprintProfile(subject_id="subject_test", database_url_env="PRIVATE_GUI_DATABASE").model_dump_json())
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(root))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return create_app(root, profile, port=8765, token="launch-test", start_monitor=False)


def authenticated(app):
    client = TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN})
    response = client.post("/auth/handshake", json={"token": "launch-test"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=strict" in response.headers["set-cookie"]
    return client


def test_boundary_auth_host_origin_and_single_use_token(app):
    client = TestClient(app, base_url=ORIGIN)
    assert client.get("/api/bootstrap").status_code == 401
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert client.post("/auth/handshake", json={"token": "launch-test"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/auth/handshake", json={"token": "launch-test"}).status_code == 403
    client = authenticated(app)
    assert client.post("/auth/handshake", json={"token": "launch-test"}).status_code == 401
    response = client.get("/api/bootstrap")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/api/bootstrap", headers={"Origin": "null"}).status_code == 403


def test_settings_compare_and_swap_and_secret_non_disclosure(app):
    client = authenticated(app)
    current = client.get("/api/bootstrap").json()
    settings = current["settings"]
    settings["theme"] = "light"
    assert client.put("/api/settings", json={"settings": settings, "revision": current["revision"]}).status_code == 200
    assert client.put("/api/settings", json={"settings": settings, "revision": current["revision"]}).status_code == 409
    response = client.post("/api/openai/key", json={"key": "test-secret-value"})
    assert response.status_code == 200
    assert "test-secret-value" not in client.get("/api/bootstrap").text
    assert "test-secret-value" not in (app.state.control.root / "operator/app-settings.json").read_text()
    assert client.request("DELETE", "/api/openai/key", json={}).status_code == 200
    assert app.state.control.api_key == ""


def test_api_file_lifecycle_and_download_is_an_attachment(app):
    client = authenticated(app)
    response = client.put("/api/files/text", json={"root": "files", "path": "note.html", "text": "<script>bad()</script>"})
    assert response.status_code == 200, response.text
    preview = client.get("/api/files/preview", params={"root": "files", "path": "note.html"}).json()
    assert preview["text"] == "<script>bad()</script>"
    content = client.get("/api/files/download", params={"root": "files", "path": "note.html"})
    assert "attachment" in content.headers["content-disposition"]
    assert content.headers["content-type"] == "application/octet-stream"
    assert client.get("/api/files/media", params={"root": "files", "path": "note.html"}).status_code == 400
    assert client.get("/api/files/preview", params={"root": "files", "path": "../profile.json"}).status_code == 400
    assert client.put("/api/files/text", json={"root": "runtime", "path": "profile.json", "text": "changed"}).status_code == 403
    trashed = client.post("/api/files/trash", json={"root": "files", "path": "note.html", "revision": preview["revision"]})
    assert trashed.status_code == 200
    assert client.post(f"/api/files/restore/{trashed.json()['id']}", json={}).status_code == 200


def test_chat_does_not_bypass_runtime_setup_and_registry_is_available(app):
    client = authenticated(app)
    assert client.post("/api/chat", json={"text": "hello", "conversation_id": str(uuid4())}).status_code == 400
    response = client.get("/api/registries")
    assert response.status_code == 200
    assert "file-scopes/v1" in response.json()["schemas"]
    assert client.get("/assets/app.js").status_code == 200
