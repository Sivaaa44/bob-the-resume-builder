"""Step 4 — the guardrail. Check every proposal against its evidence.

Evidence for a proposal = the bullet's current text (rewrites only — it's already on your
resume) + the text and skills of the facts it cites. A proposal with any `error` check is
blocked and never reaches the PDF. Warnings are shown to the human.
"""

import re

from pydantic import BaseModel, Field

from bob.llm.base import LLM
from bob.profile.model import Fact, Profile
from bob.tailor.models import Check, Coverage, JobAnalysis, Proposal
from bob.terms import contains_term, find_terms, name_like_tokens, norm, same_term
from bob.tex.model import ResumeDoc
from bob.tex.text import strip_markers

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")


def numbers_in(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER_RE.findall(text)}


def vocabulary(profile: Profile, analysis: JobAnalysis, doc: ResumeDoc) -> list[str]:
    """Every term the checker watches for: the user's skills and the JD's keywords."""
    terms = profile.all_skills() + [k for r in analysis.requirements for k in r.keywords]
    terms += [s for line in doc.skill_lines() for s in line.items]
    return list({norm(t): t for t in terms if t.strip()}.values())


class _EntailOut(BaseModel):
    supported: bool
    unsupported_claims: list[str] = Field(default_factory=list)


ENTAIL_SYSTEM = """\
You are a strict fact-checker for resumes. Given EVIDENCE and a CANDIDATE bullet, decide whether
every claim in the candidate (actions, tools, scale, numbers, outcomes) is supported by the
evidence. Rephrasing and standard synonyms are fine; added specifics are not.
"""


def verify(
    p: Proposal,
    doc: ResumeDoc,
    profile: Profile,
    analysis: JobAnalysis,
    coverage: list[Coverage],
    llm: LLM | None = None,
    text: str | None = None,
) -> list[Check]:
    """Checks for proposal `p` (or for `text` instead of its new_text, e.g. a user edit)."""
    new = strip_markers(text if text is not None else p.new_text)
    checks: list[Check] = []

    known = {f.id: f for f in profile.facts}
    cited: list[Fact] = [known[f] for f in p.fact_ids if f in known]
    unknown = [f for f in p.fact_ids if f not in known]
    if unknown:
        checks.append(Check(name="facts_exist", level="error", message=f"cites unknown facts: {', '.join(unknown)}"))
    if p.kind == "add" and not cited:
        checks.append(Check(name="facts_exist", level="error", message="a new bullet must cite at least one fact"))

    foreign = [f.id for f in cited if f.entry not in (None, p.entry_id)]
    if foreign:
        checks.append(Check(name="facts_scope", level="error",
                            message=f"uses facts from a different job/project: {', '.join(foreign)}"))

    evidence_parts = [p.original_text] if p.kind == "rewrite" else []
    evidence_parts += [f.text for f in cited] + [s for f in cited for s in f.skills]
    evidence = " | ".join(evidence_parts)

    invented_numbers = sorted(numbers_in(new) - numbers_in(evidence))
    if invented_numbers:
        checks.append(Check(name="numbers", level="error",
                            message=f"numbers not in the evidence: {', '.join(invented_numbers)}"))

    checks += _term_checks(new, evidence, p, cited, analysis, coverage, vocabulary(profile, analysis, doc))
    checks += _length_checks(new, p, doc)

    if llm is not None and not any(c.level == "error" for c in checks):
        out = llm.complete_json(ENTAIL_SYSTEM, f"EVIDENCE:\n{evidence}\n\nCANDIDATE:\n{new}", _EntailOut)
        if not out.supported:
            claims = "; ".join(out.unsupported_claims) or "unspecified"
            checks.append(Check(name="entailment", level="error", message=f"not supported by the evidence: {claims}"))
    return checks


def _term_checks(new: str, evidence: str, p: Proposal, cited: list[Fact], analysis: JobAnalysis,
                 coverage: list[Coverage], vocab: list[str]) -> list[Check]:
    """Each skill/tool/name in the new text must be in the evidence, or be a JD keyword whose
    requirement the matcher found directly covered by one of the cited facts.

    Candidates are known vocabulary terms plus name-like tokens ("Terraform", "AWS") so that
    tools nobody listed anywhere are caught too."""
    checks = []
    cited_ids = {f.id for f in cited}
    cov = {c.requirement_id: c for c in coverage}
    terms = find_terms(new, vocab)
    terms += [t for t in name_like_tokens(new) if not any(contains_term(v, t) for v in terms)]
    for term in terms:
        if contains_term(evidence, term):
            continue
        bridge = next(
            (
                (r, cov[r.id]) for r in analysis.requirements
                if any(same_term(term, k) for k in r.keywords)
                and r.id in cov and cov[r.id].strength == "direct"
                and cited_ids & set(cov[r.id].fact_ids)
            ),
            None,
        )
        if bridge is None:
            checks.append(Check(name="terms", level="error",
                                message=f"'{term}' is not supported by the cited facts"))
        else:
            r, c = bridge
            via = ", ".join(sorted(cited_ids & set(c.fact_ids)))
            checks.append(Check(name="terms", level="warning",
                                message=f"uses the JD's term '{term}' because {via} was judged to cover "
                                        f"'{r.text}' — make sure you'd defend that in an interview"))
    return checks


def _length_checks(new: str, p: Proposal, doc: ResumeDoc) -> list[Check]:
    if p.kind == "rewrite":
        limit = max(int(len(p.original_text) * 1.25), len(p.original_text) + 25)
    else:
        limit = int(max((len(b.text) for b in doc.entry(p.entry_id).bullets), default=150) * 1.1)
    if len(new) > limit:
        return [Check(name="length", level="warning",
                      message=f"{len(new)} chars (budget ~{limit}) — may wrap to an extra line")]
    return []


def verify_all(proposals: list[Proposal], doc: ResumeDoc, profile: Profile, analysis: JobAnalysis,
               coverage: list[Coverage], llm: LLM | None = None) -> list[Proposal]:
    """Attach checks to fresh proposals and set them to blocked/pending."""
    for p in proposals:
        p.checks = verify(p, doc, profile, analysis, coverage, llm)
        p.status = "blocked" if p.errors else "pending"
    return proposals
