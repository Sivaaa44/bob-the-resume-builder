"""Command-line interface: `bob <command>`."""

import argparse
import sys
from pathlib import Path

from bob.config import Settings, Workspace
from bob.profile.store import load_profile, save_profile, seed_profile
from bob.tex.model import ResumeDoc
from bob.tex.parser import parse


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

    for sp in (i, f):
        sp.add_argument("--home", help="workspace directory (default: $BOB_HOME or ./workspace)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
