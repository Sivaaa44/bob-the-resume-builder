"""Command-line interface: `bob <command>`."""

import argparse
import sys
from pathlib import Path

from bob import pipeline
from bob.config import Settings, Workspace
from bob.llm.base import LLMError
from bob.llm.openai_compat import get_llm
from bob.profile.store import ProfileError, load_profile, save_profile, seed_profile
from bob.runs import Run
from bob.tailor.match import coverage_score
from bob.tailor.models import Proposal
from bob.tex.model import ResumeDoc
from bob.tex.parser import parse

MARK = {"direct": "✓", "adjacent": "~", "none": "✗"}


def format_outline(doc: ResumeDoc) -> str:
    lines = []
    for s in doc.sections:
        lines.append(f"{s.title}  [{s.id}]")
        for e in s.entries:
            sub = f" — {e.subtitle}" if e.subtitle else ""
            lines.append(f"  {e.title}{sub}  [{e.id}]")
            for b in e.bullets:
                lines.append(f"    • {b.text}  [{b.id.rsplit('.', 1)[1]}]")
        for line in s.skill_lines:
            lines.append(f"  {line.category}: {', '.join(line.items)}  [{line.id}]")
    return "\n".join(lines)


def cmd_outline(args: argparse.Namespace) -> int:
    print(format_outline(parse(Path(args.tex).read_text(encoding="utf-8"))))
    return 0


def _workspace(args: argparse.Namespace) -> Workspace:
    return Workspace(Path(args.home)) if getattr(args, "home", None) else Settings().workspace


def load_resume(ws: Workspace) -> ResumeDoc:
    if not ws.resume_path.exists():
        raise SystemExit(f"No resume at {ws.resume_path}. Run `bob init path/to/resume.tex` first.")
    return parse(ws.resume_path.read_text(encoding="utf-8"))


def cmd_init(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    src = Path(args.tex).read_text(encoding="utf-8")
    doc = parse(src)
    if ws.profile_path.exists() and not args.force:
        print(f"{ws.profile_path} already exists (use --force to overwrite).", file=sys.stderr)
        return 1
    ws.root.mkdir(parents=True, exist_ok=True)
    ws.resume_path.write_text(src, encoding="utf-8")
    profile = seed_profile(doc)
    save_profile(profile, ws.profile_path, doc)
    print(f"Workspace ready at {ws.root}")
    print(f"  {len(doc.bullets())} bullets in {len(doc.entries())} entries → {len(profile.facts)} facts")
    print(f"Next: open {ws.profile_path}, add facts that didn't fit on the page and skill aliases.")
    return 0


def cmd_facts(args: argparse.Namespace) -> int:
    ws = _workspace(args)
    doc = load_resume(ws)
    profile = load_profile(ws.profile_path, doc)
    for e in doc.entries():
        facts = [f for f in profile.facts if f.entry == e.id]
        print(f"{e.title}  [{e.id}]  — {len(facts)} facts")
    general = [f for f in profile.facts if not f.entry]
    print(f"General — {len(general)} facts")
    print(f"Skills with evidence: {', '.join(profile.all_skills())}")
    return 0


# ---------- run reports ----------

def format_proposal(p: Proposal, ctx: pipeline.Context) -> str:
    entry = ctx.doc.entry(p.entry_id)
    status = "BLOCKED" if p.status == "blocked" else p.status
    lines = [f"[{p.id}] {p.kind} · {entry.title}  ({status})"]
    if p.kind == "rewrite":
        lines.append(f"    - {p.original_text}")
    lines.append(f"    + {p.new_text}")
    if p.status == "edited":
        lines.append(f"    ✎ {p.user_text}")
    cites = ", ".join(p.fact_ids) or "none"
    targets = ", ".join(p.requirement_ids) or "none"
    lines.append(f"    facts: {cites} · targets: {targets}" + (f" · {p.rationale}" if p.rationale else ""))
    for c in p.checks:
        lines.append(f"    {'✗' if c.level == 'error' else '⚠'} {c.name}: {c.message}")
    return "\n".join(lines)


def format_run(run: Run, ctx: pipeline.Context) -> str:
    a = run.analysis
    cov = {c.requirement_id: c for c in run.coverage}
    counts = {k: sum(1 for c in run.coverage if c.strength == k) for k in MARK}
    head = f"{a.title or 'Untitled role'}" + (f" @ {a.company}" if a.company else "")
    out = [
        f"{head}   [run {run.id}] — {run.status}",
        f"Coverage {coverage_score(a, run.coverage):.0%} (must-haves weigh double): "
        f"{counts['direct']} covered, {counts['adjacent']} partial, {counts['none']} gaps",
        "",
        "Requirements",
    ]
    for r in a.requirements:
        c = cov[r.id]
        facts = f"  ← {', '.join(c.fact_ids)}" if c.fact_ids else ""
        note = f"  ({c.note})" if c.note else ""
        out.append(f"  {MARK[c.strength]} {r.id} {r.importance:<4} {r.text}{facts}{note}")
    out += ["", f"Proposals ({len(run.proposals)})"]
    out += [format_proposal(p, ctx) for p in run.proposals] or ["  none — your resume already covers what it can"]
    if run.skills_added:
        state = "will be added" if run.include_skill_additions else "skipped"
        out += ["", f"Skills from your profile the JD asks for ({state}): {', '.join(run.skills_added)}"]
    if run.result:
        r = run.result
        out += ["", f"Built: {r.pdf_path} — {r.pages} page(s){'' if r.fits else ' (OVER BUDGET)'}"]
        for d in r.dropped:
            out.append(f"  dropped to fit: {d.text}")
    return "\n".join(out)


def _context(args: argparse.Namespace, need_llm: bool) -> pipeline.Context:
    settings = Settings()
    llm = None
    if need_llm:
        try:
            llm = get_llm(settings)
        except LLMError as e:
            raise SystemExit(str(e))
    try:
        return pipeline.load_context(_workspace(args), llm, settings)
    except (pipeline.PipelineError, ProfileError) as e:
        raise SystemExit(str(e))


def cmd_tailor(args: argparse.Namespace) -> int:
    jd = sys.stdin.read() if args.jd == "-" else Path(args.jd).read_text(encoding="utf-8")
    ctx = _context(args, need_llm=True)
    print("Reading the JD, matching your facts, drafting proposals...", file=sys.stderr)
    run = pipeline.start_run(ctx, jd, strict=args.strict)
    print(format_run(run, ctx))
    print(f"\nNext: bob review {run.id}")
    return 0


HELP = "[a]ccept  [r]eject  [e]dit  [g]enerate again  [s]kip  [q]uit"


def review_loop(ctx: pipeline.Context, run: Run, ask=input, out=print) -> None:
    """Walk through undecided proposals and record decisions."""
    todo = [p for p in run.proposals if p.status in ("pending", "blocked")]
    if not todo:
        out("Nothing left to review.")
    for p in todo:
        while True:
            out("\n" + format_proposal(p, ctx))
            if p.status == "blocked":
                out("  This proposal failed verification. You can edit it, regenerate it, or reject it.")
            choice = ask(f"  {HELP} > ").strip().lower()[:1]
            try:
                if choice == "a":
                    pipeline.decide(ctx, run, p.id, "accept")
                elif choice == "r":
                    pipeline.decide(ctx, run, p.id, "reject")
                elif choice == "e":
                    p = pipeline.decide(ctx, run, p.id, "edit", ask("  your text > "))
                    for c in p.checks:
                        out(f"    {'✗' if c.level == 'error' else '⚠'} {c.message}")
                elif choice == "g":
                    p = pipeline.regenerate(ctx, run, p.id, ask("  what should change? > "))
                    continue
                elif choice == "s":
                    pass
                elif choice == "q":
                    return
                else:
                    out(f"  {HELP}")
                    continue
            except (pipeline.PipelineError, LLMError) as e:
                out(f"  {e}")
                continue
            break


def cmd_review(args: argparse.Namespace) -> int:
    ctx = _context(args, need_llm=True)
    run = ctx.store.load(args.run)
    review_loop(ctx, run)
    print(f"\nNext: bob finalize {run.id}")
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    ctx = _context(args, need_llm=False)
    run = ctx.store.load(args.run)
    if args.accept_all:
        pipeline.accept_all_passing(ctx, run)
    if args.no_skill_additions:
        run.include_skill_additions = False
    pending = [p.id for p in run.proposals if p.status == "pending"]
    if pending:
        print(f"Leaving out undecided proposals: {', '.join(pending)}", file=sys.stderr)
    try:
        run = pipeline.finalize(ctx, run)
    except Exception as e:  # CompileError / PipelineError: show the reason, not a traceback
        print(f"Build failed: {e}", file=sys.stderr)
        return 1
    print(format_run(run, ctx))
    return 0


def cmd_runs(args: argparse.Namespace) -> int:
    ctx = _context(args, need_llm=False)
    runs = ctx.store.list()
    if not runs:
        print("No runs yet. Start one with: bob tailor jd.txt")
    for r in runs:
        role = r.analysis.title + (f" @ {r.analysis.company}" if r.analysis.company else "")
        print(f"{r.created_at[:16]}  {r.status:<15} {coverage_score(r.analysis, r.coverage):>4.0%}  {role}  [{r.id}]")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    ctx = _context(args, need_llm=False)
    print(format_run(ctx.store.load(args.run), ctx))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bob", description="Tailor a LaTeX resume to a job, truthfully.")
    sub = p.add_subparsers(dest="command", required=True)

    o = sub.add_parser("outline", help="show how Bob reads a .tex resume")
    o.add_argument("tex")
    o.set_defaults(func=cmd_outline)

    i = sub.add_parser("init", help="create a workspace from your resume and seed profile.yaml")
    i.add_argument("tex")
    i.add_argument("--force", action="store_true", help="overwrite an existing profile.yaml")
    i.set_defaults(func=cmd_init)

    f = sub.add_parser("facts", help="validate profile.yaml and summarize your facts")
    f.set_defaults(func=cmd_facts)

    t = sub.add_parser("tailor", help="analyze a JD and propose verified changes")
    t.add_argument("jd", help="file with the job description, or - for stdin")
    t.add_argument("--strict", action="store_true", help="also fact-check each proposal with the LLM")
    t.set_defaults(func=cmd_tailor)

    r = sub.add_parser("review", help="accept / reject / edit / regenerate proposals of a run")
    r.add_argument("run")
    r.set_defaults(func=cmd_review)

    fz = sub.add_parser("finalize", help="build the tailored PDF from accepted proposals")
    fz.add_argument("run")
    fz.add_argument("--accept-all", action="store_true", help="accept every proposal that passed verification")
    fz.add_argument("--no-skill-additions", action="store_true", help="don't add profile skills to the skills section")
    fz.set_defaults(func=cmd_finalize)

    rs = sub.add_parser("runs", help="list past runs (your application history)")
    rs.set_defaults(func=cmd_runs)

    sh = sub.add_parser("show", help="print a run's report")
    sh.add_argument("run")
    sh.set_defaults(func=cmd_show)

    for sp in (i, f, t, r, fz, rs, sh):
        sp.add_argument("--home", help="workspace directory (default: $BOB_HOME or ./workspace)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyError as e:  # unknown run / proposal id
        print(e.args[0] if e.args else e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
