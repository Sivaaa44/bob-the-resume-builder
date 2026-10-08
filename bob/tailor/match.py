"""Step 2 — which of the user's facts support which requirement.

The LLM judges semantic fit ("Pinecone" supports "vector databases"); code then
(a) throws away any requirement/fact id the LLM made up, and
(b) adds literal keyword hits the LLM missed. A literal hit always counts as direct.
"""

from typing import Literal

from pydantic import BaseModel, Field

from bob.llm.base import LLM
from bob.profile.model import Fact, Profile
from bob.tailor.models import Coverage, JobAnalysis, Requirement
from bob.terms import contains_term
from bob.tex.model import ResumeDoc

SYSTEM = """\
You match job requirements to a candidate's verified facts. Be strict and honest.

For each requirement decide:
- "direct": the cited facts show the candidate has done/used exactly this (synonyms and
  well-known equivalents count, e.g. "Pinecone" is a vector database).
- "adjacent": related experience that is genuinely relevant but does NOT prove the requirement
  (e.g. Docker for a Kubernetes requirement). Never stretch this.
- "none": nothing in the facts supports it.
Cite fact ids only from the list given. `note` is one short sentence a candidate would find useful
(for "none": what is missing; for "adjacent": what is and isn't covered).
"""


class _CoverageOut(BaseModel):
    requirement_id: str
    strength: Literal["direct", "adjacent", "none"]
    fact_ids: list[str] = Field(default_factory=list)
    note: str = ""


class MatchOut(BaseModel):
    coverage: list[_CoverageOut]


def _facts_block(profile: Profile, doc: ResumeDoc | None) -> str:
    titles = {e.id: e.title for e in doc.entries()} if doc else {}
    lines = []
    for f in profile.facts:
        where = titles.get(f.entry, f.entry) if f.entry else "general"
        skills = f" (skills: {', '.join(f.skills)})" if f.skills else ""
        lines.append(f"- {f.id} [{where}] {f.text}{skills}")
    return "\n".join(lines)


def _requirements_block(reqs: list[Requirement]) -> str:
    return "\n".join(f"- {r.id} ({r.importance}) {r.text} — keywords: {', '.join(r.keywords)}" for r in reqs)


def literal_hits(req: Requirement, facts: list[Fact]) -> list[str]:
    """Fact ids whose text or skills literally contain one of the requirement's keywords."""
    hits = []
    for f in facts:
        haystack = " | ".join([f.text, *f.skills])
        if any(contains_term(haystack, k) for k in req.keywords):
            hits.append(f.id)
    return hits


def match(analysis: JobAnalysis, profile: Profile, llm: LLM, doc: ResumeDoc | None = None) -> list[Coverage]:
    user = (
        f"Requirements:\n{_requirements_block(analysis.requirements)}\n\n"
        f"Candidate facts:\n{_facts_block(profile, doc)}\n\n"
        "Return one coverage item per requirement id."
    )
    out = llm.complete_json(SYSTEM, user, MatchOut)

    valid_facts = profile.fact_ids()
    by_req: dict[str, _CoverageOut] = {}
    for c in out.coverage:
        if c.requirement_id not in by_req:  # first answer wins; ignore unknown ids below
            by_req[c.requirement_id] = c

    result: list[Coverage] = []
    for req in analysis.requirements:
        llm_cov = by_req.get(req.id)
        fact_ids = [f for f in (llm_cov.fact_ids if llm_cov else []) if f in valid_facts]
        strength = llm_cov.strength if llm_cov and fact_ids else "none"
        note = llm_cov.note.strip() if llm_cov else ""

        literal = literal_hits(req, profile.facts)
        if literal:
            strength = "direct"
            fact_ids = list(dict.fromkeys(fact_ids + literal))
        result.append(
            Coverage(requirement_id=req.id, strength=strength, fact_ids=list(dict.fromkeys(fact_ids)),
                     note=note, literal=bool(literal))
        )
    return result


def gaps(analysis: JobAnalysis, coverage: list[Coverage]) -> list[tuple[Requirement, Coverage]]:
    """Requirements with no direct evidence, must-haves first."""
    by_id = {c.requirement_id: c for c in coverage}
    return [(r, by_id[r.id]) for r in analysis.requirements if by_id[r.id].strength != "direct"]


def coverage_score(analysis: JobAnalysis, coverage: list[Coverage]) -> float:
    """Weighted share of requirements directly covered (must = 2, nice = 1)."""
    by_id = {c.requirement_id: c for c in coverage}
    weights = {r.id: 2 if r.importance == "must" else 1 for r in analysis.requirements}
    total = sum(weights.values())
    hit = sum(w for rid, w in weights.items() if by_id[rid].strength == "direct")
    return hit / total if total else 0.0
