"""Step 3 — ask the LLM for small, independent bullet proposals.

The LLM sees plain-text bullets and facts (never LaTeX) and returns proposals:
  rewrite: rephrase an existing bullet so it speaks the JD's language
  add:     bring in a fact from the same entry that isn't on the page yet
Code then drops anything that points at ids that don't exist or changes nothing.
"""

from typing import Literal

from pydantic import BaseModel, Field

from bob.llm.base import LLM
from bob.profile.model import Profile
from bob.tailor.models import Coverage, JobAnalysis, Proposal
from bob.tex.model import ResumeDoc

MAX_PROPOSALS = 8

SYSTEM = """\
You tailor resume bullets to a job description WITHOUT inventing anything.

You get: the job's requirements (with which facts cover them), the resume's entries with their
current bullets, and for each entry the candidate's verified facts.

Propose at most {max_proposals} changes, only where they help a requirement:
- "rewrite": rephrase one existing bullet (give bullet_id). Use the JD's wording for things the
  bullet's facts already prove. Keep it about the same length (one line on the page).
- "add": add one new bullet to an entry (give entry_id) built from that entry's facts that are
  not on the resume yet, when it covers a requirement the current bullets don't.

Hard rules — a separate checker rejects any proposal that breaks them:
1. Every claim must come from the facts you cite in fact_ids. For a rewrite, the bullet's own
   current text also counts as evidence.
2. Only cite facts listed under the same entry, or general facts.
3. Never introduce a number, metric, tool, technology or skill that is not in the cited facts.
4. Copy numbers exactly as written in the facts.
5. Plain text only, no LaTeX. You may wrap 1-2 key JD terms in **double asterisks** for bold.
6. Start with a strong past-tense verb. No first person.
"""


class _ProposalOut(BaseModel):
    kind: Literal["rewrite", "add"]
    bullet_id: str | None = None
    entry_id: str | None = None
    new_text: str
    fact_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class PlanOut(BaseModel):
    proposals: list[_ProposalOut]


def build_prompt(doc: ResumeDoc, profile: Profile, analysis: JobAnalysis, coverage: list[Coverage],
                 focus_bullet: str | None = None, focus_entry: str | None = None,
                 feedback: str | None = None) -> str:
    cov = {c.requirement_id: c for c in coverage}
    parts = ["REQUIREMENTS"]
    for r in analysis.requirements:
        c = cov.get(r.id)
        support = "none" if not c else c.strength + (f" via {', '.join(c.fact_ids)}" if c.fact_ids else "")
        parts.append(f"- {r.id} ({r.importance}) {r.text} | keywords: {', '.join(r.keywords)} | coverage: {support}")

    parts.append("\nRESUME ENTRIES")
    for e in doc.entries():
        if not e.bullets:
            continue
        if focus_entry and e.id != focus_entry:
            continue
        parts.append(f"\n## {e.id} — {e.title}" + (f" ({e.subtitle})" if e.subtitle else ""))
        on_page = {b.text for b in e.bullets}
        for b in e.bullets:
            parts.append(f"  bullet {b.id}: {b.text}")
        for f in profile.facts:
            if f.entry == e.id:
                tag = "on resume" if f.text in on_page else "NOT on resume"
                skills = f" (skills: {', '.join(f.skills)})" if f.skills else ""
                parts.append(f"  fact {f.id} [{tag}]: {f.text}{skills}")

    general = [f for f in profile.facts if not f.entry]
    if general:
        parts.append("\nGENERAL FACTS (usable in any entry)")
        parts += [f"  fact {f.id}: {f.text}" for f in general]

    if focus_bullet:
        parts.append(f"\nReturn exactly one proposal: a rewrite of bullet {focus_bullet}.")
    elif focus_entry:
        parts.append(f"\nReturn exactly one proposal: an add to entry {focus_entry}.")
    if feedback:
        parts.append(f"\nThe candidate gave this feedback on the previous attempt — follow it:\n{feedback}")
    return "\n".join(parts)


def normalize(raw: list[_ProposalOut], doc: ResumeDoc, analysis: JobAnalysis, limit: int) -> list[Proposal]:
    """Turn raw LLM proposals into Proposals, dropping ones that reference unknown ids or change nothing."""
    bullets = {b.id: b for b in doc.bullets()}
    entries = {e.id: e for e in doc.entries()}
    req_ids = {r.id for r in analysis.requirements}
    out: list[Proposal] = []
    seen_bullets: set[str] = set()
    for p in raw:
        text = " ".join(p.new_text.split())
        if not text:
            continue
        reqs = [r for r in dict.fromkeys(p.requirement_ids) if r in req_ids]
        facts = list(dict.fromkeys(p.fact_ids))
        if p.kind == "rewrite":
            b = bullets.get(p.bullet_id or "")
            if not b or b.id in seen_bullets or text.replace("**", "") == b.text:
                continue
            seen_bullets.add(b.id)
            out.append(Proposal(id="", kind="rewrite", entry_id=b.entry_id, bullet_id=b.id,
                                original_text=b.text, new_text=text, fact_ids=facts,
                                requirement_ids=reqs, rationale=p.rationale.strip()))
        else:
            e = entries.get(p.entry_id or "")
            if not e or not e.bullets or text.replace("**", "") in {b.text for b in e.bullets}:
                continue
            out.append(Proposal(id="", kind="add", entry_id=e.id, new_text=text, fact_ids=facts,
                                requirement_ids=reqs, rationale=p.rationale.strip()))
        if len(out) == limit:
            break
    return out


def plan(doc: ResumeDoc, profile: Profile, analysis: JobAnalysis, coverage: list[Coverage], llm: LLM,
         max_proposals: int = MAX_PROPOSALS) -> list[Proposal]:
    out = llm.complete_json(SYSTEM.format(max_proposals=max_proposals),
                            build_prompt(doc, profile, analysis, coverage), PlanOut)
    proposals = normalize(out.proposals, doc, analysis, max_proposals)
    for k, p in enumerate(proposals, start=1):
        p.id = f"p{k}"
    return proposals


def replan_one(target: Proposal, feedback: str, doc: ResumeDoc, profile: Profile, analysis: JobAnalysis,
               coverage: list[Coverage], llm: LLM) -> Proposal | None:
    """Regenerate a single proposal with the user's feedback. Keeps the same id."""
    prompt = build_prompt(doc, profile, analysis, coverage,
                          focus_bullet=target.bullet_id if target.kind == "rewrite" else None,
                          focus_entry=target.entry_id if target.kind == "add" else None,
                          feedback=f"Previous attempt: {target.new_text}\nFeedback: {feedback}")
    out = llm.complete_json(SYSTEM.format(max_proposals=1), prompt, PlanOut)
    wanted = [p for p in out.proposals if p.kind == target.kind]
    if target.kind == "rewrite":
        wanted = [p for p in wanted if p.bullet_id == target.bullet_id]
    else:
        wanted = [p.model_copy(update={"entry_id": target.entry_id}) for p in wanted]
    new = normalize(wanted, doc, analysis, 1)
    if not new:
        return None
    new[0].id = target.id
    return new[0]
