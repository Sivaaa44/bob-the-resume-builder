import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def resume_src() -> str:
    return (FIXTURES / "resume.tex").read_text(encoding="utf-8")


def pdflatex_pages(tex: str, tmp_path: Path) -> int:
    """Compile with pdflatex and return the page count (test helper; skips if TeX is absent)."""
    if not shutil.which("pdflatex"):
        pytest.skip("pdflatex not installed")
    from pypdf import PdfReader

    (tmp_path / "r.tex").write_text(tex, encoding="utf-8")
    res = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "r.tex"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
    )
    assert res.returncode == 0, res.stdout[-2000:]
    return len(PdfReader(tmp_path / "r.pdf").pages)


@pytest.fixture
def doc(resume_src):
    from bob.tex.parser import parse

    return parse(resume_src)


@pytest.fixture
def profile(doc):
    """Seeded facts f1..f10 plus two user-added facts."""
    from bob.profile.model import Fact
    from bob.profile.store import seed_profile

    p = seed_profile(doc)
    p.facts.append(Fact(id="f11", text="Indexed 50k support tickets in Pinecone for semantic search",
                        entry="experience.data-engineering-intern", skills=["Pinecone"]))
    p.facts.append(Fact(id="f12", text="AWS Certified Cloud Practitioner (2024)", skills=["AWS"]))
    return p


@pytest.fixture
def analysis():
    from bob.tailor.models import JobAnalysis, Requirement

    return JobAnalysis(title="ML Engineer", company="Initech", requirements=[
        Requirement(id="r1", text="Strong Python", importance="must", keywords=["Python"]),
        Requirement(id="r2", text="Vector databases", importance="must", keywords=["vector databases"]),
        Requirement(id="r3", text="Kubernetes in production", importance="must", keywords=["Kubernetes"]),
        Requirement(id="r4", text="Snowflake data warehousing", importance="nice", keywords=["Snowflake"]),
    ])


ACME = "experience.data-engineering-intern"
GLOBEX = "experience.automation-intern"


def scripted_llm():
    """A FakeLLM that plays a realistic run over the fixture resume and jd.txt."""
    from bob.llm.fake import FakeLLM
    from bob.tailor.analyze import JDExtraction
    from bob.tailor.match import MatchOut
    from bob.tailor.plan import PlanOut

    return FakeLLM({
        JDExtraction: {"title": "Machine Learning Engineer", "company": "Initech", "requirements": [
            {"text": "Strong Python", "importance": "must", "keywords": ["Python"]},
            {"text": "Vector databases", "importance": "must", "keywords": ["vector databases"]},
            {"text": "Kubernetes in production", "importance": "must", "keywords": ["Kubernetes"]},
            {"text": "Snowflake data warehousing", "importance": "nice", "keywords": ["Snowflake"]},
        ]},
        MatchOut: {"coverage": [
            {"requirement_id": "r2", "strength": "direct", "fact_ids": ["f11"], "note": "Pinecone is a vector DB"},
            {"requirement_id": "r3", "strength": "none", "note": "No container orchestration experience listed"},
        ]},
        PlanOut: {"proposals": [
            {"kind": "rewrite", "bullet_id": f"{ACME}.b1", "fact_ids": ["f1"], "requirement_ids": ["r1"],
             "new_text": "Cut report generation time by 40% with a multi-agent **Python** pipeline"},
            {"kind": "add", "entry_id": ACME, "fact_ids": ["f11"], "requirement_ids": ["r2"],
             "new_text": "Indexed 50k support tickets in a **vector database** (Pinecone) for semantic search"},
            {"kind": "rewrite", "bullet_id": f"{ACME}.b3", "fact_ids": ["f3"], "requirement_ids": ["r3"],
             "new_text": "Deployed MCP server tools for LLM agents on Kubernetes"},
            {"kind": "rewrite", "bullet_id": f"{GLOBEX}.b2", "fact_ids": ["f5"],
             "new_text": "Saved the finance team 15 hours/week by automating manual data entry"},
        ]},
    })


@pytest.fixture
def workspace(tmp_path, resume_src, profile, doc):
    """An initialized workspace containing the fixture resume and profile (with f11, f12)."""
    from bob.config import Workspace
    from bob.profile.store import save_profile

    ws = Workspace(tmp_path / "ws")
    ws.root.mkdir()
    ws.resume_path.write_text(resume_src, encoding="utf-8")
    profile.skills["Tools"] = profile.skills["Tools"] + ["Kubernetes"]  # pretend: user listed it but has no story
    save_profile(profile, ws.profile_path, doc)
    return ws
