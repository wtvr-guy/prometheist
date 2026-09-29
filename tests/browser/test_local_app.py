"""Real browser + real local API/file I/O; model-service metadata is a fixture."""
import json
import os
from pathlib import Path
import shutil
import socket
import threading
import time

import pytest
import uvicorn

pytestmark = pytest.mark.skipif(os.environ.get("PROMETHEIST_BROWSER_TESTS") != "1", reason="explicit browser acceptance job")


@pytest.fixture
def local_app(tmp_path, monkeypatch):
    from prometheist.gui_server import create_app
    from prometheist.imprinting import ImprintProfile
    from prometheist import gui_models
    profile = tmp_path / "profile.json"
    profile.write_text(ImprintProfile(subject_id="subject_001", database_url_env="PRIVATE_BROWSER_DATABASE").model_dump_json())
    root = tmp_path / "artifacts"
    root.mkdir()
    monkeypatch.setenv("PROMETHEIST_ARTIFACT_ROOT", str(root))
    models = [{"name": "qwen3:4b", "size": 2500000000, "details": {"parameter_size": "4.0B", "quantization_level": "Q4_K_M"}},
              {"name": "gemma3:4b", "size": 3300000000, "details": {"parameter_size": "4.3B", "quantization_level": "Q4_K_M"}}]
    monkeypatch.setattr(gui_models, "installed_models", lambda endpoint: models)
    def details(endpoint, name):
        from prometheist.model_parameters import parameter_catalog
        metadata = {"capabilities": ["completion", "thinking"], "model_info": {"test.context_length": 32768}}
        return {"model": name, "parameters": "temperature 0.6\ntop_p 0.95", "details": {}, **metadata, "controls": parameter_catalog("ollama", name, metadata)}
    monkeypatch.setattr(gui_models, "model_details", details)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    app = create_app(root, profile, port=port, token="browser-test-token", start_monitor=False)
    app.state.control.ready = True
    app.state.control.health = {"status": "ready", "message": "Private runtime ready"}
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(.02)
    assert server.started
    yield f"http://127.0.0.1:{port}/#token=browser-test-token", app
    server.should_exit = True
    thread.join(timeout=10)


def test_navigation_controls_and_persistent_file_workflow(local_app, tmp_path):
    from playwright.sync_api import sync_playwright, expect
    url, app = local_app
    screenshots = Path(os.environ.get("PROMETHEIST_SCREENSHOTS", str(tmp_path / "screenshots")))
    screenshots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        executable = os.environ.get("PROMETHEIST_BROWSER_BINARY") or shutil.which("google-chrome") or shutil.which("chromium")
        browser = playwright.chromium.launch(headless=True, executable_path=executable, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        expect(page.get_by_role("heading", name="A private space to think clearly.")).to_be_visible()
        page.screenshot(path=str(screenshots / "chat-desktop.png"), full_page=True)
        assert "token=" not in page.url
        page.get_by_role("button", name="Controls", exact=True).click()
        expect(page.get_by_role("heading", name="Generation", exact=True)).to_be_visible()
        page.get_by_role("switch", name="Override Temperature", exact=True).check()
        page.get_by_role("spinbutton", name="Temperature", exact=True).fill("0.45")
        page.get_by_role("button", name="Save overrides", exact=True).click()
        expect(page.get_by_role("status").filter(has_text="Generation overrides saved")).to_be_visible()
        assert app.state.control.settings.selection.parameters["temperature"] == .45
        page.get_by_role("button", name="Close generation controls").click()
        page.get_by_role("button", name="Models", exact=True).click()
        expect(page.get_by_role("heading", name="qwen3:4b", exact=True)).to_be_visible()
        page.screenshot(path=str(screenshots / "models-desktop.png"), full_page=True)
        page.get_by_role("button", name="Files", exact=True).click()
        page.get_by_role("button", name="New folder", exact=True).click()
        page.get_by_role("textbox", name="Folder name", exact=True).fill("Notes")
        page.get_by_role("button", name="Create", exact=True).click()
        expect(page.get_by_role("button", name="Notes", exact=True)).to_be_visible()
        page.get_by_role("button", name="Notes", exact=True).click()
        page.get_by_role("button", name="New text file", exact=True).click()
        page.get_by_role("textbox", name="File name", exact=True).fill("first-note.md")
        page.get_by_role("textbox", name="New file content", exact=True).fill("A persistent note.\n<script>window.pwned = true</script>")
        page.get_by_role("button", name="Create", exact=True).click()
        expect(page.get_by_role("button", name="first-note.md", exact=True)).to_be_visible()
        page.get_by_role("button", name="first-note.md", exact=True).click()
        expect(page.get_by_role("textbox", name="Contents of first-note.md")).to_have_value("A persistent note.\n<script>window.pwned = true</script>")
        assert page.evaluate("window.pwned") is None
        page.get_by_role("textbox", name="Contents of first-note.md").fill("An edited persistent note.")
        page.get_by_role("button", name="Save changes", exact=True).click()
        expect(page.get_by_role("status").filter(has_text="The previous content")).to_be_visible()
        assert (app.state.control.files.workspace / "Notes/first-note.md").read_text() == "An edited persistent note."
        page.locator('input[type="file"]').set_input_files({"name": "uploaded.txt", "mimeType": "text/plain", "buffer": b"upload survives reload"})
        expect(page.get_by_role("button", name="uploaded.txt", exact=True)).to_be_visible()
        page.reload()
        page.get_by_role("button", name="Files", exact=True).click()
        page.get_by_role("button", name="Notes", exact=True).click()
        expect(page.get_by_role("button", name="uploaded.txt", exact=True)).to_be_visible()
        page.screenshot(path=str(screenshots / "files-desktop.png"), full_page=True)
        with page.expect_download() as download:
            page.get_by_role("link", name="Download uploaded.txt", exact=True).click()
        assert Path(download.value.path()).read_bytes() == b"upload survives reload"
        page.get_by_role("button", name="Move uploaded.txt to Trash", exact=True).click()
        page.get_by_role("button", name="Move to Trash", exact=True).click()
        expect(page.get_by_role("button", name="uploaded.txt", exact=True)).to_have_count(0)
        page.get_by_role("button", name="File activity", exact=True).click()
        page.get_by_role("button", name="Restore", exact=True).click()
        expect(page.get_by_role("status").filter(has_text="Restored to its original path")).to_be_visible()
        page.get_by_role("button", name="Close dialog", exact=True).click()
        expect(page.get_by_role("button", name="uploaded.txt", exact=True)).to_be_visible()
        page.get_by_role("button", name="Settings", exact=True).click()
        page.screenshot(path=str(screenshots / "settings-desktop.png"), full_page=True)
        page.get_by_role("button", name="Privacy & consent", exact=True).click()
        expect(page.get_by_role("heading", name="No external destinations authorized")).to_be_visible()
        page.get_by_role("button", name="Chat", exact=True).click()
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(screenshots / "chat-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.get_by_role("button", name="Toggle navigation").click()
        page.get_by_role("button", name="Files", exact=True).click()
        expect(page.get_by_role("heading", name="Files", exact=True)).to_be_visible()
        page.screenshot(path=str(screenshots / "files-mobile.png"), full_page=True)
        assert not errors, json.dumps(errors)
        browser.close()
