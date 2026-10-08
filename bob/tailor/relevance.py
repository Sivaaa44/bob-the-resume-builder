"""Deterministic relevance: how much a bullet helps with this JD. Used for ordering and for
deciding what to drop when the page overflows. No LLM involved."""

from bob.profile.model import Profile
from bob.tailor.models import JobAnalysis
from bob.terms import contains_term
from bob.tex.model import ResumeDoc

WEIGHT = {"must": 2.0, "nice": 1.0}


def score_text(text: str, analysis: JobAnalysis, extra_requirement_ids: list[str] = ()) -> float:
    """Sum of requirement weights this text addresses (by keyword, or explicitly via a proposal)."""
    total = 0.0
    for r in analysis.requirements:
        if r.id in extra_requirement_ids or any(contains_term(text, k) for k in r.keywords):
            total += WEIGHT[r.importance]
    return total


def order_by_score(ids: list[str], scores: dict[str, float]) -> list[str]:
    """Highest score first; ties keep their original order (stable)."""
    return sorted(ids, key=lambda i: -scores.get(i, 0.0))


def tailor_skills(doc: ResumeDoc, profile: Profile, analysis: JobAnalysis) -> tuple[dict[str, list[str]], list[str]]:
    """For each skills line: JD-relevant skills first, plus skills from the same category of the
    profile that the JD asks for but the resume doesn't list yet.

    Returns (line id → new items, list of added skills).
    """
    keywords = [k for r in analysis.requirements for k in r.keywords]

    def relevant(skill: str) -> bool:
        return any(contains_term(skill, k) or contains_term(k, skill) for k in keywords)

    on_resume = {s.lower() for line in doc.skill_lines() for s in line.items}
    result: dict[str, list[str]] = {}
    added: list[str] = []
    for line in doc.skill_lines():
        extra = [s for s in profile.skills.get(line.category, [])
                 if s.lower() not in on_resume and relevant(s)]
        items = line.items + extra
        added += extra
        on_resume |= {s.lower() for s in extra}
        result[line.id] = sorted(items, key=lambda s: not relevant(s))
    return result, added
