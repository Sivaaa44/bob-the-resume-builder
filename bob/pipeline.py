"""The whole flow, top to bottom. CLI and API are thin wrappers around these functions.

    start_run   JD → analyze → match → plan → verify          (status: awaiting_review)
    decide      human accepts / rejects / edits one proposal
    regenerate  human asks for another attempt at one proposal, with feedback
    finalize    apply accepted proposals → order → fit page → compile PDF   (status: finalized)
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bob.build.compile import CompileResult, compile_tex
from bob.build.fit import fit
from bob.config import Settings, Workspace
from bob.llm.base import LLM, Usage
from bob.profile.model import Profile
from bob.profile.store import load_profile
from bob.runs import BuildResult, DroppedBullet, Run, RunStore, now_iso
from bob.tailor.analyze import analyze_jd
from bob.tailor.match import match
from bob.tailor.models import Proposal
from bob.tailor.plan import plan, replan_one
from bob.tailor.relevance import order_by_score, score_text, tailor_skills
from bob.tailor.verify import verify, verify_all
from bob.tex.editor import Edits, NewBullet
from bob.tex.model import ResumeDoc
from bob.tex.parser import parse

CompileFn = Callable[..., CompileResult]
ACCEPTED_BONUS = 0.5  # a bullet the human just approved should outlive an equally relevant untouched one


class PipelineError(RuntimeError):
    pass


@dataclass
class Context:
    ws: Workspace
    doc: ResumeDoc
    profile: Profile
    llm: LLM | None = None
    settings: Settings | None = None

    @property
    def store(self) -> RunStore:
        return RunStore(self.ws.runs_dir)

    @property
    def resume_sha(self) -> str:
        return hashlib.sha256(self.doc.source.encode()).hexdigest()[:16]

    @property
    def max_pages(self) -> int:
        return self.settings.max_pages if self.settings else 1


def load_context(ws: Workspace, llm: LLM | None = None, settings: Settings | None = None) -> Context:
    if not ws.resume_path.exists() or not ws.profile_path.exists():
        raise PipelineError(f"Workspace {ws.root} is not set up. Run `bob init path/to/resume.tex` first.")
    doc = parse(ws.resume_path.read_text(encoding="utf-8"))
    profile = load_profile(ws.profile_path, doc, persist_ids=True)  # runs cite fact ids, so they must stick
    return Context(ws=ws, doc=doc, profile=profile, llm=llm, settings=settings)


class _Meter:
    """Tokens used per step, measured as the change in the client's running total."""

    def __init__(self, llm: LLM):
        self.llm = llm
        self.steps: dict[str, Usage] = {}

    def run(self, step: str, fn, *args, **kwargs):
        before = getattr(self.llm, "usage", Usage())
        try:
            return fn(*args, **kwargs)
        finally:
            used = getattr(self.llm, "usage", Usage()).minus(before)
            if used.calls:
                self.steps[step] = self.steps.get(step, Usage()).add(used)


def _need_llm(ctx: Context) -> LLM:
    if ctx.llm is None:
        raise PipelineError("this step needs an LLM (set BOB_LLM_API_KEY)")
    return ctx.llm


def start_run(ctx: Context, jd_text: str, strict: bool = False) -> Run:
    """Analyze the JD and produce verified proposals. `strict` adds an LLM fact-check per proposal."""
    if not jd_text.strip():
        raise PipelineError("the job description is empty")
    llm = _need_llm(ctx)
    meter = _Meter(llm)
    analysis = meter.run("analyze", analyze_jd, jd_text, llm)
    coverage = meter.run("match", match, analysis, ctx.profile, llm, ctx.doc)
    proposals = meter.run("plan", plan, ctx.doc, ctx.profile, analysis, coverage, llm)
    meter.run("verify", verify_all, proposals, ctx.doc, ctx.profile, analysis, coverage, llm if strict else None)
    _, skills_added = tailor_skills(ctx.doc, ctx.profile, analysis)

    run = Run(id=ctx.store.new_id(analysis), created_at=now_iso(), jd_text=jd_text,
              resume_sha=ctx.resume_sha, analysis=analysis, coverage=coverage,
              proposals=proposals, skills_added=skills_added, token_usage=meter.steps)
    ctx.store.save(run)
    return run


Action = Literal["accept", "reject", "edit", "reset"]


def decide(ctx: Context, run: Run, proposal_id: str, action: Action, text: str | None = None) -> Proposal:
    """Record the human's decision on one proposal.

    Blocked proposals can't be accepted as written — edit them instead. Your own edits are
    applied (you are the source of truth) but still checked, so you see any warnings.
    """
    p = run.proposal(proposal_id)
    if action == "accept":
        if p.status == "blocked":
            raise PipelineError(f"{p.id} failed verification; edit it or add the missing fact to profile.yaml")
        p.status = "accepted"
    elif action == "reject":
        p.status = "rejected"
    elif action == "edit":
        if not text or not text.strip():
            raise PipelineError("edit needs the new text")
        p.user_text = " ".join(text.split())
        p.checks = verify(p, ctx.doc, ctx.profile, run.analysis, run.coverage, text=p.user_text)
        p.status = "edited"
    elif action == "reset":
        p.user_text = None
        p.checks = verify(p, ctx.doc, ctx.profile, run.analysis, run.coverage)
        p.status = "blocked" if p.errors else "pending"
    else:
        raise PipelineError(f"unknown action: {action}")
    if run.status == "finalized":
        run.status = "awaiting_review"  # decisions changed; the PDF needs rebuilding
    ctx.store.save(run)
    return p


def accept_all_passing(ctx: Context, run: Run) -> int:
    n = 0
    for p in run.proposals:
        if p.status == "pending":
            p.status = "accepted"
            n += 1
    ctx.store.save(run)
    return n


def regenerate(ctx: Context, run: Run, proposal_id: str, feedback: str, strict: bool = False) -> Proposal:
    llm = _need_llm(ctx)
    old = run.proposal(proposal_id)
    meter = _Meter(llm)
    try:
        new = meter.run("regenerate", replan_one, old, feedback, ctx.doc, ctx.profile, run.analysis, run.coverage, llm)
        if new is None:
            raise PipelineError("the model didn't return a usable proposal; try different feedback")
        new.checks = meter.run("regenerate", verify, new, ctx.doc, ctx.profile, run.analysis, run.coverage,
                               llm if strict else None)
    finally:
        for step, used in meter.steps.items():
            run.record_usage(step, used)
    new.status = "blocked" if new.errors else "pending"
    run.proposals[run.proposals.index(old)] = new
    if run.status == "finalized":
        run.status = "awaiting_review"
    ctx.store.save(run)
    return new


def build_edits(ctx: Context, run: Run) -> tuple[Edits, dict[str, float], list[str]]:
    """Accepted proposals → Edits, relevance scores for every bullet, and the skills added."""
    edits = Edits()
    applied = {p.bullet_id: p for p in run.proposals if p.kind == "rewrite" and p.status in ("accepted", "edited")}
    scores: dict[str, float] = {}
    # a bullet only gets credit for requirements you have evidence for (an edit may have removed the claim)
    supported = {c.requirement_id for c in run.coverage if c.strength != "none"}

    def targets(p: Proposal) -> list[str]:
        return [r for r in p.requirement_ids if r in supported]

    for e in ctx.doc.entries():
        ids = []
        for b in e.bullets:
            p = applied.get(b.id)
            text = p.final_text if p else b.text
            if p:
                edits.rewrites[b.id] = text
            scores[b.id] = score_text(text, run.analysis, targets(p) if p else []) + (ACCEPTED_BONUS if p else 0)
            ids.append(b.id)
        for p in run.proposals:
            if p.kind == "add" and p.entry_id == e.id and p.status in ("accepted", "edited"):
                nid = f"{e.id}.{p.id}"
                edits.adds.setdefault(e.id, []).append(NewBullet(nid, p.final_text))
                scores[nid] = score_text(p.final_text, run.analysis, targets(p)) + ACCEPTED_BONUS
                ids.append(nid)
        if ids:
            edits.orders[e.id] = order_by_score(ids, scores)

    skills, added = tailor_skills(ctx.doc, ctx.profile, run.analysis)
    if not run.include_skill_additions:
        skills = {lid: [s for s in items if s not in added] for lid, items in skills.items()}
        added = []
    edits.skills = skills
    return edits, scores, added


def finalize(ctx: Context, run: Run, compile_fn: CompileFn | None = None) -> Run:
    if run.status == "aborted":
        raise PipelineError("this run was aborted")
    if run.resume_sha != ctx.resume_sha:
        raise PipelineError("resume.tex changed since this run started; start a new run for this JD")

    compile_fn = compile_fn or compile_tex
    edits, scores, added = build_edits(ctx, run)
    out_dir = ctx.store.run_dir(run.id)
    search = [ctx.ws.root]

    def measure(tex: str) -> int:
        return compile_fn(tex, out_dir / "_fit", name="tailored", search_dirs=search).pages

    fitted = fit(ctx.doc, edits, scores, measure, max_pages=ctx.max_pages)
    final = compile_fn(fitted.tex, out_dir, name="tailored", search_dirs=search)

    texts = {b.id: edits.rewrites.get(b.id, b.text) for b in ctx.doc.bullets()} | {
        n.id: n.text for adds in edits.adds.values() for n in adds
    }
    run.result = BuildResult(
        pages=final.pages, fits=final.pages <= ctx.max_pages,
        dropped=[DroppedBullet(id=d, text=texts.get(d, "")) for d in fitted.dropped],
        skills_added=added, tex_path=str(out_dir / "tailored.tex"), pdf_path=str(Path(final.pdf_path)),
    )
    run.status = "finalized"
    ctx.store.save(run)
    return run


def abort(ctx: Context, run: Run) -> Run:
    run.status = "aborted"
    ctx.store.save(run)
    return run
