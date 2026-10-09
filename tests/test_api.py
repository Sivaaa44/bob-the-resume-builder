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
    assert client.get("/api/health").json() == {"ok": True, "workspace_ready": True}
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
