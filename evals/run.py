"""Live eval: run real tailoring on fixed cases with your configured model and score the output.

    python -m evals.run                     # all cases in evals/cases/
    python -m evals.run --case poor_fit     # one case
    python -m evals.run --model gemini-2.5-pro

Uses the same LLM settings as the app (.env or workspace/settings.json). Writes a JSON report to
evals/results/ and prints a table. Exit code 1 if any fabrication leaked through.

Run it before/after every prompt or model change and compare the tables.
"""

import argparse
import json
import sys
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import yaml

from bob import pipeline
from bob.config import Settings, Workspace
from bob.llm.base import LLMError
from bob.llm.openai_compat import get_llm
from bob.profile.model import Fact
from bob.profile.store import save_profile
from bob.runs import Run
from bob.setup import init_workspace
from bob.terms import contains_term, same_term

ROOT = Path(__file__).resolve().parent.parent
CASES = Path(__file__).parent / "cases"
RESULTS = Path(__file__).parent / "results"


def _requirement_for(run: Run, keyword: str):
    for r in run.analysis.requirements:
        if any(same_term(keyword, k) for k in r.keywords) or contains_term(r.text, keyword):
            return r
    return None


def score_run(run: Run, ctx: pipeline.Context, expect: dict) -> dict:
    """Grade one run against a case's expectations. Pure function: easy to test."""
    cov = {c.requirement_id: c for c in run.coverage}

    covered = []
    for k in expect.get("must_cover", []):
        r = _requirement_for(run, k)
        covered.append(bool(r and cov[r.id].strength == "direct"))
    gapped = []
    for k in expect.get("must_gap", []):
        r = _requirement_for(run, k)
        gapped.append(r is None or cov[r.id].strength != "direct")  # never claimed as covered

    passed = [p for p in run.proposals if p.status != "blocked"]
    titles = {e.id: e.title for e in ctx.doc.entries()}
    leaks = []
    for p in passed:
        for term in expect.get("forbidden", []):
            if contains_term(p.final_text, term):
                leaks.append((p.id, term))
        for title_prefix, terms in (expect.get("entry_forbidden") or {}).items():
            if titles.get(p.entry_id, "").startswith(title_prefix):
                leaks += [(p.id, t) for t in terms if contains_term(p.final_text, t)]

    return {
        "requirements": len(run.analysis.requirements),
        "coverage_hits": sum(covered), "coverage_expected": len(covered),
        "gap_hits": sum(gapped), "gap_expected": len(gapped),
        "proposals": len(run.proposals), "passed": len(passed), "blocked": len(run.proposals) - len(passed),
        "leaks": leaks,
        "tokens": run.total_usage.total, "calls": run.total_usage.calls,
    }


def run_case(path: Path, settings: Settings, llm=None) -> dict:
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        ws = Workspace(Path(tmp))
        result = init_workspace(ws, (ROOT / case["resume"]).read_text(encoding="utf-8"))
        profile = result.profile
        for i, f in enumerate(case.get("extra_facts", []), start=1):
            profile.facts.append(Fact(id=f"x{i}", source="user", **f))
        save_profile(profile, ws.profile_path, result.doc)

        ctx = pipeline.load_context(ws, llm or get_llm(settings), settings)
        started = time.monotonic()
        try:
            run = pipeline.start_run(ctx, case["jd"])
        except LLMError as e:
            return {"case": path.stem, "error": str(e)[:300], "seconds": round(time.monotonic() - started, 1)}
        return {"case": path.stem, "seconds": round(time.monotonic() - started, 1),
                **score_run(run, ctx, case.get("expect", {}))}


def table(rows: list[dict]) -> str:
    head = "| case | cover | gaps | proposals (blocked) | leaks | tokens | sec |\n|---|---|---|---|---|---|---|"
    lines = [head]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['case']} | ERROR: {r['error'][:60]} | | | | | {r['seconds']} |")
            continue
        leaks = ", ".join(f"{p}:{t}" for p, t in r["leaks"]) or "0"
        lines.append(f"| {r['case']} | {r['coverage_hits']}/{r['coverage_expected']} | {r['gap_hits']}/{r['gap_expected']} "
                     f"| {r['proposals']} ({r['blocked']}) | {leaks} | {r['tokens']:,} | {r['seconds']} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.run", description=__doc__.split("\n\n")[0])
    ap.add_argument("--case", action="append", help="case name (file stem); repeatable. Default: all")
    ap.add_argument("--model", help="override the configured model")
    ap.add_argument("--home", help="workspace whose settings.json to use (default: $BOB_HOME or ./workspace)")
    args = ap.parse_args(argv)

    settings = Settings.load(args.home or Settings().home)
    if args.model:
        settings = replace(settings, llm_model=args.model)
    paths = sorted(CASES.glob("*.yaml"))
    if args.case:
        paths = [p for p in paths if p.stem in args.case]
    if not paths:
        print("No matching cases.", file=sys.stderr)
        return 2

    print(f"Model: {settings.llm_model} @ {settings.llm_base_url}\n", file=sys.stderr)
    rows = []
    for p in paths:
        print(f"  running {p.stem}…", file=sys.stderr)
        rows.append(run_case(p, settings))
    print(table(rows))

    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = RESULTS / f"{stamp}-{settings.llm_model.replace('/', '_')}.json"
    out.write_text(json.dumps({"model": settings.llm_model, "base_url": settings.llm_base_url, "rows": rows}, indent=2))
    print(f"\nSaved {out.relative_to(ROOT)}", file=sys.stderr)
    return 1 if any(r.get("leaks") for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
