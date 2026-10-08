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
