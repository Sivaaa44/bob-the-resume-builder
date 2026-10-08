import pytest

from bob.build.compile import CompileError, compile_tex, latex_errors
from bob.build.fit import fit
from bob.tailor.relevance import order_by_score, score_text, tailor_skills
from bob.tex.editor import Edits, NewBullet
from tests.conftest import pdflatex_pages

ACME = "experience.data-engineering-intern"


# ---------- relevance ----------

def test_score_text(analysis):
    assert score_text("Built pipelines in Python on Snowflake", analysis) == 3.0   # r1 must + r4 nice
    assert score_text("Organized a hackathon", analysis) == 0.0
    assert score_text("Indexed tickets in Pinecone", analysis, ["r2"]) == 2.0       # explicit target


def test_order_by_score_is_stable():
    assert order_by_score(["a", "b", "c", "d"], {"b": 2, "c": 2, "d": 1}) == ["b", "c", "d", "a"]


def test_tailor_skills_reorders_and_adds_from_profile(doc, profile, analysis):
    profile.skills["Tools"] = profile.skills["Tools"] + ["Kubernetes", "Jira"]
    lines, added = tailor_skills(doc, profile, analysis)
    assert lines["technical-skills.tools"] == ["Snowflake", "Kubernetes", "Git", "Docker", "ServiceNow"]
    assert lines["technical-skills.languages"][0] == "Python"
    assert added == ["Kubernetes"]  # Jira isn't asked for, so it isn't added


# ---------- fit loop (fake page counter) ----------

def fake_measure(limit_bullets: int):
    """Pretend the page holds `limit_bullets` bullets; each extra one spills to page 2."""
    def measure(tex: str) -> int:
        n = tex.count("\\resumeItem{") + tex.count("\\item ") - 1  # minus the \resumeItem definition
        return 1 if n <= limit_bullets else 2
    return measure


def test_fit_noop_when_it_fits(doc):
    r = fit(doc, Edits(), {}, fake_measure(100))
    assert (r.pages, r.dropped, r.fits, r.tex) == (1, [], True, doc.source)


def test_fit_drops_lowest_relevance_first(doc):
    total = len(doc.bullets())
    scores = {b.id: 5.0 for b in doc.bullets()}
    scores["leadership.items.b2"] = 0.0
    scores[f"{ACME}.b2"] = 1.0
    r = fit(doc, Edits(), scores, fake_measure(total - 2))
    assert r.dropped == ["leadership.items.b2", f"{ACME}.b2"] and r.fits
    assert "Mentored 6" not in r.tex


def test_fit_ties_drop_from_the_bottom_and_keeps_one_bullet_per_entry(doc):
    r = fit(doc, Edits(), {}, fake_measure(0), max_drops=50)
    assert r.dropped[0] == "leadership.items.b2"         # bottom of the page goes first
    remaining = {e.id for e in doc.entries() if e.bullets}
    assert len(r.dropped) == len(doc.bullets()) - len(remaining)  # one bullet left per entry
    assert not r.fits


def test_fit_removes_added_bullets_instead_of_dropping(doc):
    edits = Edits(adds={ACME: [NewBullet("new1", "Low value add")]})
    r = fit(doc, edits, {"new1": 0.0, **{b.id: 1.0 for b in doc.bullets()}}, fake_measure(len(doc.bullets())))
    assert r.dropped == ["new1"] and "Low value add" not in r.tex
    assert edits.adds[ACME]  # caller's edits are not mutated


# ---------- real compile ----------

def test_compile_fixture(resume_src, tmp_path):
    pdflatex_pages(resume_src, tmp_path)  # skips when TeX is missing
    res = compile_tex(resume_src, tmp_path / "out", name="r")
    assert res.pages == 1 and res.pdf_path.exists()


def test_compile_error_is_readable(resume_src, tmp_path):
    pdflatex_pages(resume_src, tmp_path)
    broken = resume_src.replace("\\section{Projects}", "\\section{Projects}\\undefinedmacro")
    with pytest.raises(CompileError) as e:
        compile_tex(broken, tmp_path / "bad")
    assert "Undefined control sequence" in str(e.value)


def test_latex_errors_extracts_bang_lines():
    log = "noise\n! Missing $ inserted.\nl.12 foo_bar\nmore\n"
    assert latex_errors(log).startswith("! Missing $ inserted.")


def test_real_overflow_is_fit_to_one_page(doc, resume_src, tmp_path):
    pdflatex_pages(resume_src, tmp_path)
    filler = "Did a long, low-relevance thing that wraps onto a second line of the page so it takes room " * 2
    edits = Edits(adds={ACME: [NewBullet(f"new{i}", filler) for i in range(14)]})
    scores = {f"new{i}": 0.0 for i in range(14)} | {b.id: 1.0 for b in doc.bullets()}
    measure = lambda tex: compile_tex(tex, tmp_path / "fit", name="m").pages  # noqa: E731
    r = fit(doc, edits, scores, measure, max_drops=14)
    assert r.fits and r.pages == 1
    assert r.dropped and all(d.startswith("new") for d in r.dropped)
