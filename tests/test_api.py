import pytest
from fastapi.testclient import TestClient

from bob.api import create_app
from bob.llm.base import LLMError
from tests.conftest import ACME, scripted_llm
from tests.test_pipeline import fake_compile


@pytest.fixture
def client(workspace):
    return TestClient(create_app(workspace, llm_factory=scripted_llm, compile_fn=fake_compile(1)))


def test_health_resume_profile(client):
    health = client.get("/api/health").json()
    assert health["ok"] and health["workspace_ready"]
    resume = client.get("/api/resume").json()
    assert "source" not in resume
    assert resume["sections"][1]["entries"][0]["id"] == ACME
    assert any(f["id"] == "f11" for f in client.get("/api/profile").json()["facts"])


def test_full_flow_over_http(client):
    r = client.post("/api/runs", json={"jd_text": "JD"})
    assert r.status_code == 201
    run = r.json()
    rid = run["id"]
    assert run["score"] == pytest.approx(5 / 7, abs=1e-3)
    assert run["tokens"]["calls"] == 3 and run["tokens"]["total"] > 0
    assert [p["status"] for p in run["proposals"]] == ["pending", "pending", "blocked", "pending"]

    assert client.post(f"/api/runs/{rid}/proposals/p3", json={"action": "accept"}).status_code == 400
    edited = client.post(f"/api/runs/{rid}/proposals/p3",
                         json={"action": "edit", "text": "Exposed internal tools to LLM agents via an MCP server"}).json()
    assert edited["proposals"][2]["status"] == "edited"
    client.post(f"/api/runs/{rid}/proposals/p4", json={"action": "reject"})
    client.patch(f"/api/runs/{rid}", json={"include_skill_additions": False})
    after = client.post(f"/api/runs/{rid}/accept-all").json()
    assert [p["status"] for p in after["proposals"]] == ["accepted", "accepted", "edited", "rejected"]

    assert client.get(f"/api/runs/{rid}/pdf").status_code == 404  # not built yet
    done = client.post(f"/api/runs/{rid}/finalize").json()
    assert done["status"] == "finalized" and done["result"]["pages"] == 1
    pdf = client.get(f"/api/runs/{rid}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["content-disposition"].startswith("inline")  # previews in an iframe
    assert "Indexed 50k support tickets" in client.get(f"/api/runs/{rid}/tex").text

    listed = client.get("/api/runs").json()
    assert listed[0]["id"] == rid and listed[0]["company"] == "Initech"


def test_regenerate_over_http(client):
    rid = client.post("/api/runs", json={"jd_text": "JD"}).json()["id"]
    assert client.post(f"/api/runs/{rid}/proposals/p3", json={"action": "regenerate"}).status_code == 400
    # scripted_llm replans with the same PlanOut, which contains a p3-targeting rewrite again
    r = client.post(f"/api/runs/{rid}/proposals/p3", json={"action": "regenerate", "feedback": "no Kubernetes"})
    assert r.status_code == 200 and r.json()["proposals"][2]["id"] == "p3"


def test_errors_map_to_status_codes(workspace):
    def broken_llm():
        raise LLMError("No LLM API key")

    c = TestClient(create_app(workspace, llm_factory=broken_llm))
    assert c.post("/api/runs", json={"jd_text": "JD"}).status_code == 502
    assert c.get("/api/runs/does-not-exist").status_code == 404
    assert c.get("/api/runs/BAD..id").status_code == 404
    ok = TestClient(create_app(workspace, llm_factory=scripted_llm))
    assert ok.post("/api/runs", json={"jd_text": "  "}).status_code == 400


# ---------- setup, facts editor, settings, stats ----------

from bob.config import Settings, Workspace  # noqa: E402
from tests.conftest import FIXTURES  # noqa: E402


@pytest.fixture
def empty(tmp_path):
    ws = Workspace(tmp_path / "fresh")
    return ws, TestClient(create_app(ws, llm_factory=scripted_llm, compile_fn=fake_compile(1)))


def test_setup_preview_does_not_write(empty):
    ws, c = empty
    assert c.get("/api/health").json()["workspace_ready"] is False
    tex = (FIXTURES / "custom_headings.tex").read_text()
    r = c.post("/api/setup/preview", json={"tex": tex}).json()
    assert r["stats"] == {"sections": 1, "entries": 3, "bullets": 5, "skill_lines": 0}
    assert any("skills section" in w for w in r["warnings"])
    assert r["outline"]["sections"][0]["entries"][1]["title"].startswith("AMD")
    assert not ws.root.exists()


def test_setup_import_then_reimport_keeps_user_facts(empty):
    ws, c = empty
    tex = (FIXTURES / "resume.tex").read_text()
    first = c.post("/api/setup/import", json={"tex": tex}).json()
    assert first["facts"] == 10 and first["kept"] == 0 and ws.ready
    prof = c.get("/api/profile").json()
    prof["facts"].append({"text": "Led the campus ACM chapter", "entry": "leadership.items", "skills": ["Leadership"]})
    c.put("/api/profile", json=prof)
    again = c.post("/api/setup/import", json={"tex": tex}).json()
    assert again["kept"] == 1
    assert any(f["text"] == "Led the campus ACM chapter" for f in c.get("/api/profile").json()["facts"])


def test_setup_rejects_unparseable_tex(empty):
    _, c = empty
    r = c.post("/api/setup/preview", json={"tex": "hello"})
    assert r.status_code == 400 and "Couldn't read" in r.json()["detail"]


def test_profile_editor_assigns_ids_and_validates(client):
    prof = client.get("/api/profile").json()
    prof["facts"].append({"text": "  Speaks Tamil and English ", "skills": ["Tamil", " "]})
    prof["facts"].append({"text": "   "})  # blank rows from the editor are dropped
    saved = client.put("/api/profile", json=prof).json()
    new = saved["facts"][-1]
    assert new["text"] == "Speaks Tamil and English" and new["skills"] == ["Tamil"] and new["id"].startswith("f")
    assert new["source"] == "user" and new["entry"] is None

    prof["facts"].append({"text": "x", "entry": "experience.nope"})
    r = client.put("/api/profile", json=prof)
    assert r.status_code == 400 and "unknown resume entry" in r.json()["detail"]


def test_settings_roundtrip_never_returns_the_key(empty, monkeypatch):
    ws, c = empty
    monkeypatch.delenv("BOB_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert c.get("/api/settings").json()["has_key"] is False
    r = c.put("/api/settings", json={"llm_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                                     "llm_model": " gemini-2.5-flash ", "llm_api_key": "AIzaSECRET1234"}).json()
    assert r["has_key"] and r["key_hint"] == "…1234" and r["llm_model"] == "gemini-2.5-flash"
    assert "SECRET" not in str(r)
    assert Settings.load(ws.root).llm_api_key == "AIzaSECRET1234"   # saved for CLI + API
    assert c.get("/api/health").json()["has_llm_key"] is True
    # blank key in a later save keeps the existing one
    c.put("/api/settings", json={"llm_model": "gemini-2.5-pro", "llm_api_key": ""})
    assert Settings.load(ws.root).llm_api_key == "AIzaSECRET1234"
    assert c.put("/api/settings", json={"max_pages": 9}).status_code == 400


def test_settings_file_overrides_env(tmp_path, monkeypatch):
    from bob.config import save_settings

    monkeypatch.setenv("BOB_LLM_MODEL", "from-env")
    ws = Workspace(tmp_path)
    assert Settings.load(tmp_path).llm_model == "from-env"
    save_settings(ws, llm_model="from-ui", max_pages=2)
    s = Settings.load(tmp_path)
    assert (s.llm_model, s.max_pages) == ("from-ui", 2)


def test_settings_connection_test(workspace):
    from bob.api import _Ping
    from bob.llm.fake import FakeLLM

    good = TestClient(create_app(workspace, llm_factory=lambda: FakeLLM({_Ping: {"ok": True}})))
    assert good.post("/api/settings/test").json()["ok"] is True

    def bad_key():
        raise LLMError("LLM API returned 401: invalid key")

    r = TestClient(create_app(workspace, llm_factory=bad_key)).post("/api/settings/test")
    assert r.status_code == 502 and "401" in r.json()["detail"]


def test_stats(client):
    assert client.get("/api/stats").json()["runs"] == 0
    rid = client.post("/api/runs", json={"jd_text": "JD"}).json()["id"]
    client.post(f"/api/runs/{rid}/proposals/p1", json={"action": "accept"})
    client.post(f"/api/runs/{rid}/proposals/p2", json={"action": "reject"})
    client.post(f"/api/runs/{rid}/proposals/p3", json={"action": "edit", "text": "Exposed tools via an MCP server"})
    s = client.get("/api/stats").json()
    assert (s["runs"], s["kept"], s["edited"], s["rejected"]) == (1, 2, 1, 1)
    assert s["acceptance_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert s["avg_tokens_per_run"] > 0
