"""Workspace setup shared by `bob init` and the web UI: import a resume, sanity-check how it
was read, and seed profile.yaml while keeping facts the user wrote by hand."""

from dataclasses import dataclass, field

from bob.config import Workspace
from bob.profile.model import Fact, Profile
from bob.profile.store import ProfileError, load_profile, save_profile, seed_profile
from bob.tex.model import ResumeDoc
from bob.tex.parser import parse

MANY_BULLETS = 8  # more than this under one heading usually means several jobs were merged


def outline_warnings(doc: ResumeDoc) -> list[str]:
    """Things worth a human glance before trusting the parse."""
    warnings = []
    if not doc.bullets():
        warnings.append("Bob found no bullet points. Your template may use bullet macros Bob doesn't know yet.")
    for e in doc.entries():
        if len(e.bullets) > MANY_BULLETS:
            warnings.append(f"'{e.title}' has {len(e.bullets)} bullets. If that's several jobs merged into one, "
                            "Bob didn't recognise their headings.")
        if not e.title.strip() or e.title == e.section_id:
            warnings.append(f"An entry in '{e.section_id}' has no title Bob could read.")
    if not doc.skill_lines():
        warnings.append("No skills section in the `\\textbf{Category}{: a, b}` format, so Bob won't reorder or add skills.")
    return warnings


def outline_stats(doc: ResumeDoc) -> dict:
    return {"sections": len(doc.sections), "entries": len(doc.entries()),
            "bullets": len(doc.bullets()), "skill_lines": len(doc.skill_lines())}


@dataclass
class InitResult:
    doc: ResumeDoc
    profile: Profile
    kept: list[Fact] = field(default_factory=list)       # hand-written facts carried over
    orphaned: list[Fact] = field(default_factory=list)   # hand-written facts whose entry no longer exists


def _user_facts(ws: Workspace, doc: ResumeDoc) -> tuple[list[Fact], list[Fact]]:
    if not ws.profile_path.exists():
        return [], []
    try:
        old = load_profile(ws.profile_path)  # no doc: entry ids may have changed
    except ProfileError:
        return [], []
    entry_ids = {e.id for e in doc.entries()}
    user = [f for f in old.facts if f.source == "user"]
    return ([f for f in user if f.entry is None or f.entry in entry_ids],
            [f for f in user if f.entry is not None and f.entry not in entry_ids])


def init_workspace(ws: Workspace, source: str) -> InitResult:
    """Copy the resume in, seed one fact per bullet, and keep any facts the user added before."""
    doc = parse(source)  # raises ParseError before anything is written
    kept, orphaned = _user_facts(ws, doc)
    ws.root.mkdir(parents=True, exist_ok=True)
    ws.resume_path.write_text(source, encoding="utf-8")
    profile = seed_profile(doc)
    taken = profile.fact_ids()
    for f in kept:  # give a hand-written fact a fresh id if a seeded fact took its old one
        if f.id in taken:
            n = len(taken) + 1
            while f"u{n}" in taken:
                n += 1
            f.id = f"u{n}"
        taken.add(f.id)
        profile.facts.append(f)
    save_profile(profile, ws.profile_path, doc)
    return InitResult(doc=doc, profile=profile, kept=kept, orphaned=orphaned)
