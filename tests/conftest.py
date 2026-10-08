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
