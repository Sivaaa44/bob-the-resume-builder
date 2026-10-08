"""Command-line interface: `bob <command>`."""

import argparse
import sys
from pathlib import Path

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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bob", description="Tailor a LaTeX resume to a job, truthfully.")
    sub = p.add_subparsers(dest="command", required=True)

    o = sub.add_parser("outline", help="show how Bob reads a .tex resume")
    o.add_argument("tex")
    o.set_defaults(func=cmd_outline)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
