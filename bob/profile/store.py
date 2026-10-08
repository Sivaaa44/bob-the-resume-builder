"""Read/write profile.yaml, and seed it from a parsed resume.

profile.yaml is meant to be edited by hand, so it is grouped by resume entry:

    skills:
      Languages: [Python, SQL]
    entries:
      experience.data-engineering-intern:      # Data Engineering Intern — Acme Analytics
      - id: f1
        text: Built a multi-agent pipeline in Python that cut report generation time by 40%
        skills: [Python]
    general:
    - text: Comfortable presenting to non-technical stakeholders   # id is assigned on load
"""

import re
from pathlib import Path

import yaml

from bob.profile.model import Fact, Profile
from bob.tex.model import ResumeDoc
from bob.terms import find_terms

HEADER = """\
# Bob's source of truth. Everything Bob writes on your resume must be backed by a fact here.
#
# - Facts under `entries:` belong to that resume entry (job/project); Bob will only use them there.
# - Facts under `general:` can support any entry (e.g. certifications, coursework).
# - `skills:` on a fact lists the tools/terms it proves. Add aliases you'd be comfortable
#   defending in an interview, e.g. Pinecone fact → skills: [Pinecone, vector databases].
# - Add facts that didn't fit on the page — Bob can bring them in when a job asks for them.
# - `id` is optional for new facts; Bob assigns one.
"""


class ProfileError(ValueError):
    pass


class _Dumper(yaml.SafeDumper):
    """Block style for facts, inline style for short string lists like skills."""


_Dumper.add_representer(
    list,
    lambda d, data: d.represent_sequence(
        "tag:yaml.org,2002:seq", data, flow_style=all(isinstance(x, str) for x in data) and bool(data)
    ),
)


def seed_profile(doc: ResumeDoc) -> Profile:
    """One fact per existing bullet (the resume is already true), plus the skills section."""
    skills: dict[str, list[str]] = {}
    for line in doc.skill_lines():
        skills.setdefault(line.category, []).extend(line.items)
    vocab = [s for items in skills.values() for s in items]

    facts: list[Fact] = []
    for entry in doc.entries():
        stack = [s.strip() for s in entry.subtitle.split(",")] if "," in entry.subtitle else []
        if stack:  # project heading tech list, e.g. "FastAPI, React, SQLite"
            facts.append(Fact(id=f"f{len(facts) + 1}", text=f"{entry.title} was built with {entry.subtitle}",
                              entry=entry.id, skills=stack, source="resume"))
        for b in entry.bullets:
            facts.append(Fact(id=f"f{len(facts) + 1}", text=b.text, entry=entry.id,
                              skills=find_terms(b.text, vocab + stack), source="resume"))
    return Profile(facts=facts, skills=skills)


def _assign_missing_ids(raw_facts: list[dict]) -> None:
    used = {str(f["id"]) for f in raw_facts if f.get("id")}
    n = max([int(m.group(1)) for i in used if (m := re.fullmatch(r"f(\d+)", i))], default=0)
    for f in raw_facts:
        if not f.get("id"):
            n += 1
            while f"f{n}" in used:
                n += 1
            f["id"] = f"f{n}"
            used.add(f["id"])


def load_profile(path: Path, doc: ResumeDoc | None = None) -> Profile:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ProfileError(f"{path}: invalid YAML: {e}") from e
    if not isinstance(data, dict):
        raise ProfileError(f"{path}: expected a mapping with skills/entries/general")

    raw: list[dict] = []
    for entry_id, items in (data.get("entries") or {}).items():
        for item in items or []:
            raw.append({**_as_dict(item, path), "entry": entry_id})
    for item in data.get("general") or []:
        raw.append({**_as_dict(item, path), "entry": None})
    _assign_missing_ids(raw)

    try:
        profile = Profile(facts=[Fact(**f) for f in raw], skills=data.get("skills") or {})
    except Exception as e:  # pydantic ValidationError → readable message
        raise ProfileError(f"{path}: {e}") from e
    validate_profile(profile, doc)
    return profile


def _as_dict(item, path: Path) -> dict:
    if isinstance(item, str):
        return {"text": item}
    if isinstance(item, dict):
        return dict(item)
    raise ProfileError(f"{path}: each fact must be a string or a mapping, got {item!r}")


def validate_profile(profile: Profile, doc: ResumeDoc | None = None) -> None:
    errors = []
    seen: set[str] = set()
    for f in profile.facts:
        if f.id in seen:
            errors.append(f"duplicate fact id {f.id}")
        seen.add(f.id)
        if not f.text.strip():
            errors.append(f"fact {f.id} has empty text")
    if doc is not None:
        entry_ids = {e.id for e in doc.entries()}
        for f in profile.facts:
            if f.entry and f.entry not in entry_ids:
                errors.append(f"fact {f.id} refers to unknown resume entry '{f.entry}'")
    if errors:
        raise ProfileError("invalid profile:\n  - " + "\n  - ".join(errors))


def dump_profile(profile: Profile, doc: ResumeDoc | None = None) -> str:
    titles = {e.id: e.title + (f" — {e.subtitle}" if e.subtitle else "") for e in doc.entries()} if doc else {}

    def fact_dict(f: Fact) -> dict:
        d = {"id": f.id, "text": f.text}
        if f.skills:
            d["skills"] = f.skills
        if f.source == "resume":
            d["source"] = "resume"
        return d

    def block(obj) -> str:
        return yaml.dump(obj, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100)

    out = [HEADER, block({"skills": profile.skills}), "entries:\n"]
    order = [e.id for e in doc.entries()] if doc else []
    grouped: dict[str, list[Fact]] = {}
    for f in profile.facts:
        if f.entry:
            grouped.setdefault(f.entry, []).append(f)
    for entry_id in sorted(grouped, key=lambda k: (order.index(k) if k in order else len(order), k)):
        comment = f"  # {titles[entry_id]}" if entry_id in titles else ""
        out.append(f"  {entry_id}:{comment}\n")
        body = block([fact_dict(f) for f in grouped[entry_id]])
        out.append("".join(f"  {line}\n" for line in body.splitlines()))
    general = [fact_dict(f) for f in profile.facts if not f.entry]
    out.append(block({"general": general}) if general else "general: []\n")
    return "".join(out)


def save_profile(profile: Profile, path: Path, doc: ResumeDoc | None = None) -> None:
    Path(path).write_text(dump_profile(profile, doc), encoding="utf-8")
