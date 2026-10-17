"""The verifier corpus (evals/verifier_corpus.yaml) must classify every case correctly,
and the live-eval scorer must grade runs correctly."""

from pathlib import Path

import pytest
import yaml

from bob.tailor.models import Coverage, Proposal
from bob.tailor.verify import verify

CORPUS = yaml.safe_load((Path(__file__).parent.parent / "evals" / "verifier_corpus.yaml").read_text())["cases"]

COVERAGE = [
    Coverage(requirement_id="r1", strength="direct", fact_ids=["f1"], literal=True),
    Coverage(requirement_id="r2", strength="direct", fact_ids=["f11"]),
    Coverage(requirement_id="r3", strength="none"),
    Coverage(requirement_id="r4", strength="direct", fact_ids=["f2"], literal=True),
]


def _proposal(case: dict, doc) -> Proposal:
    if "bullet" in case:
        b = doc.bullet(case["bullet"])
        return Proposal(id="p", kind="rewrite", entry_id=b.entry_id, bullet_id=b.id, original_text=b.text,
                        new_text=case["text"], fact_ids=case["facts"])
    return Proposal(id="p", kind="add", entry_id=case["entry"], new_text=case["text"], fact_ids=case["facts"])


@pytest.mark.parametrize("case", CORPUS, ids=[c["name"] for c in CORPUS])
def test_verifier_corpus(case, doc, profile, analysis):
    checks = verify(_proposal(case, doc), doc, profile, analysis, COVERAGE)
    errors = {c.name for c in checks if c.level == "error"}
    if case["expect"] == "pass":
        assert not errors, f"honest rewrite was blocked: {[c.message for c in checks]}"
    else:
        assert case["check"] in errors, f"fabrication slipped through (got {errors or 'no errors'})"


def test_corpus_is_balanced():
    kinds = [c["expect"] for c in CORPUS]
    assert kinds.count("pass") >= 5 and kinds.count("block") >= 10


# ---------- live eval scoring ----------

def test_score_run_counts_leaks_and_coverage(workspace):
    from bob import pipeline
    from evals.run import score_run
    from tests.conftest import scripted_llm

    ctx = pipeline.load_context(workspace, scripted_llm())
    run = pipeline.start_run(ctx, "JD")
    expect = {"must_cover": ["Python", "vector databases"], "must_gap": ["Kubernetes"],
              "forbidden": ["Kubernetes", "Terraform"]}
    s = score_run(run, ctx, expect)
    assert s["coverage_hits"] == 2 and s["coverage_expected"] == 2
    assert s["gap_hits"] == 1 and s["gap_expected"] == 1
    assert s["leaks"] == []                        # the Kubernetes rewrite was blocked, so it isn't a leak
    assert s["blocked"] == 1 and s["passed"] == 3

    run.proposals[2].status = "pending"           # pretend the verifier had let it through
    run.proposals[2].checks = []
    assert score_run(run, ctx, expect)["leaks"] == [("p3", "Kubernetes")]


def test_live_harness_runs_a_case_end_to_end():
    from bob.config import Settings
    from evals.run import CASES, run_case, table
    from tests.conftest import scripted_llm

    row = run_case(CASES / "strong_fit.yaml", Settings(), llm=scripted_llm())
    assert "error" not in row and row["case"] == "strong_fit"
    assert row["proposals"] == 4 and row["leaks"] == []
    assert "| strong_fit |" in table([row])


def test_every_live_case_is_well_formed():
    from evals.run import CASES, ROOT
    from bob.tex.parser import parse

    for path in CASES.glob("*.yaml"):
        case = yaml.safe_load(path.read_text())
        assert case["jd"].strip() and case["expect"]["forbidden"], path.name
        parse((ROOT / case["resume"]).read_text())
