"""The guardrail: each test is a way an LLM could lie on your resume, and must be caught."""

import pytest

from bob.llm.fake import FakeLLM
from bob.tailor.models import Coverage, Proposal
from bob.tailor.plan import PlanOut, build_prompt, normalize, plan, replan_one
from bob.tailor.verify import _EntailOut, verify, verify_all
from bob.terms import name_like_tokens

ACME = "experience.data-engineering-intern"
GLOBEX = "experience.automation-intern"


@pytest.fixture
def coverage():
    return [
        Coverage(requirement_id="r1", strength="direct", fact_ids=["f1"], literal=True),
        Coverage(requirement_id="r2", strength="direct", fact_ids=["f11"], note="Pinecone is a vector DB"),
        Coverage(requirement_id="r3", strength="none"),
        Coverage(requirement_id="r4", strength="direct", fact_ids=["f2"], literal=True),
    ]


def rewrite(bullet_n: int, text: str, facts: list[str], doc, entry=ACME) -> Proposal:
    b = doc.bullet(f"{entry}.b{bullet_n}")
    return Proposal(id="p1", kind="rewrite", entry_id=entry, bullet_id=b.id,
                    original_text=b.text, new_text=text, fact_ids=facts)


def add(text: str, facts: list[str], entry=ACME) -> Proposal:
    return Proposal(id="p1", kind="add", entry_id=entry, new_text=text, fact_ids=facts)


@pytest.fixture
def check(doc, profile, analysis, coverage):
    def run(p: Proposal, llm=None):
        return verify(p, doc, profile, analysis, coverage, llm)
    return run


def errors(checks):
    return {c.name for c in checks if c.level == "error"}


# ---------- honest proposals pass ----------

def test_honest_rewrite_passes(doc, check):
    p = rewrite(1, "Cut report generation time by 40% with a multi-agent **Python** pipeline", ["f1"], doc)
    assert check(p) == []


def test_units_next_to_numbers_are_not_tools(doc, check):
    p = rewrite(2, "Transformed 2M+ rows of sales data with SQL in Snowflake", ["f2"], doc)
    assert check(p) == []


def test_general_fact_usable_anywhere(check):
    assert errors(check(add("Earned AWS Certified Cloud Practitioner (2024)", ["f12"], entry="leadership.items"))) == set()


def test_jd_term_allowed_via_direct_coverage_with_warning(check):
    p = add("Indexed 50k support tickets in a **vector database** (Pinecone) for semantic search", ["f11"])
    checks = check(p)
    assert errors(checks) == set()
    assert any(c.name == "terms" and c.level == "warning" and "vector database" in c.message for c in checks)


# ---------- fabrications are blocked ----------

def test_invented_number(doc, check):
    p = rewrite(1, "Cut report generation time by 60% with a multi-agent Python pipeline", ["f1"], doc)
    assert errors(check(p)) == {"numbers"}


def test_invented_jd_tool(doc, check):
    p = rewrite(1, "Built a multi-agent Python pipeline on Kubernetes, cutting report time by 40%", ["f1"], doc)
    c = check(p)
    assert errors(c) == {"terms"} and "Kubernetes" in c[0].message


def test_invented_tool_nobody_listed(doc, check):
    p = rewrite(1, "Built a multi-agent Python pipeline deployed with Terraform, cutting report time 40%", ["f1"], doc)
    assert "Terraform" in " ".join(c.message for c in check(p) if c.level == "error")


def test_jd_term_without_covering_fact_is_blocked(check):
    # same wording as the passing case, but citing a fact that doesn't cover r2
    p = add("Built a multi-agent Python pipeline backed by a vector database", ["f1"])
    assert "terms" in errors(check(p))


def test_borrowing_another_jobs_fact(doc, check):
    p = rewrite(3, "Automated invoice approvals with ServiceNow via an MCP server", ["f4"], doc)
    assert "facts_scope" in errors(check(p))


def test_unknown_fact_and_unsupported_add(check):
    assert "facts_exist" in errors(check(add("Led a team", ["f999"])))
    assert "facts_exist" in errors(check(add("Led a team", [])))


def test_length_warning(doc, check):
    long = "Built a multi-agent Python pipeline that cut report generation time by 40% " * 2
    c = check(rewrite(1, long, ["f1"], doc))
    assert [x.name for x in c if x.level == "warning"] == ["length"]


def test_llm_entailment_judge(doc, check):
    p = rewrite(1, "Built a multi-agent Python pipeline that cut report generation time by 40% for executives", ["f1"], doc)
    llm = FakeLLM({_EntailOut: {"supported": False, "unsupported_claims": ["for executives"]}})
    assert "entailment" in errors(check(p, llm))
    # judge is skipped when deterministic checks already failed
    bad = rewrite(1, "Cut time by 99%", ["f1"], doc)
    llm2 = FakeLLM({})
    assert errors(check(bad, llm2)) == {"numbers"} and llm2.calls == []


def test_verify_all_sets_status(doc, profile, analysis, coverage):
    good = rewrite(1, "Cut report generation time by 40% with a multi-agent Python pipeline", ["f1"], doc)
    bad = rewrite(2, "Wrote SQL on Kubernetes", ["f2"], doc)
    verify_all([good, bad], doc, profile, analysis, coverage)
    assert (good.status, bad.status) == ("pending", "blocked")


def test_name_like_tokens():
    assert name_like_tokens("Built ETL on AWS. Then used Node.js and 2M+ rows") == ["ETL", "AWS", "Node.js"]


# ---------- planning ----------

def test_prompt_is_plain_text_and_marks_unused_facts(doc, profile, analysis, coverage):
    prompt = build_prompt(doc, profile, analysis, coverage)
    assert "fact f11 [NOT on resume]" in prompt and "fact f1 [on resume]" in prompt
    assert "\\resumeItem" not in prompt and "\\textbf" not in prompt
    assert "r2 (must) Vector databases | keywords: vector databases | coverage: direct via f11" in prompt
    assert "education.state-university" not in prompt  # entries without bullets can't be edited


def test_normalize_drops_bad_proposals(doc, analysis):
    raw = PlanOut(proposals=[
        {"kind": "rewrite", "bullet_id": f"{ACME}.b1", "new_text": "  Cut  time by 40%  ", "fact_ids": ["f1", "f1"],
         "requirement_ids": ["r1", "r77"]},
        {"kind": "rewrite", "bullet_id": f"{ACME}.b1", "new_text": "duplicate target"},
        {"kind": "rewrite", "bullet_id": "nope.b1", "new_text": "unknown bullet"},
        {"kind": "rewrite", "bullet_id": f"{ACME}.b2", "new_text": doc.bullet(f"{ACME}.b2").text},  # no-op
        {"kind": "add", "entry_id": "education.state-university", "new_text": "no list to add to"},
        {"kind": "add", "entry_id": ACME, "new_text": "Indexed 50k tickets in Pinecone", "fact_ids": ["f11"]},
        {"kind": "add", "entry_id": GLOBEX, "new_text": "over the limit"},
    ]).proposals
    out = normalize(raw, doc, analysis, limit=2)
    assert [(p.kind, p.bullet_id or p.entry_id, p.new_text) for p in out] == [
        ("rewrite", f"{ACME}.b1", "Cut time by 40%"),
        ("add", ACME, "Indexed 50k tickets in Pinecone"),
    ]
    assert out[0].fact_ids == ["f1"] and out[0].requirement_ids == ["r1"]
    assert out[0].original_text == doc.bullet(f"{ACME}.b1").text


def test_plan_assigns_ids(doc, profile, analysis, coverage):
    llm = FakeLLM({PlanOut: {"proposals": [
        {"kind": "rewrite", "bullet_id": f"{ACME}.b1", "new_text": "A", "fact_ids": ["f1"]},
        {"kind": "add", "entry_id": ACME, "new_text": "B", "fact_ids": ["f11"]},
    ]}})
    assert [p.id for p in plan(doc, profile, analysis, coverage, llm)] == ["p1", "p2"]


def test_replan_one_keeps_id_and_target(doc, profile, analysis, coverage):
    target = rewrite(1, "old attempt", ["f1"], doc)
    target.id = "p7"
    llm = FakeLLM({PlanOut: [
        {"proposals": [
            {"kind": "rewrite", "bullet_id": f"{ACME}.b2", "new_text": "wrong bullet"},
            {"kind": "rewrite", "bullet_id": f"{ACME}.b1", "new_text": "Shorter: cut report time 40% in Python", "fact_ids": ["f1"]},
        ]},
        {"proposals": []},
    ]})
    new = replan_one(target, "make it shorter", doc, profile, analysis, coverage, llm)
    assert (new.id, new.bullet_id, new.new_text) == ("p7", f"{ACME}.b1", "Shorter: cut report time 40% in Python")
    assert "make it shorter" in llm.calls[0][1] and "rewrite of bullet" in llm.calls[0][1]
    assert replan_one(target, "again", doc, profile, analysis, coverage, llm) is None
