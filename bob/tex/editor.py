"""Apply structured edits to a ResumeDoc and render new LaTeX.

Only the spans of entries/skill lines that actually change are rewritten; the rest of
the file (preamble, headings, spacing, comments) is copied byte-for-byte.
"""

from dataclasses import dataclass, field

from bob.tex.model import Entry, ResumeDoc
from bob.tex.text import to_latex


class EditError(ValueError):
    pass


@dataclass
class NewBullet:
    id: str      # caller-chosen, e.g. "experience.acme.new1"; usable in `orders`
    text: str    # plain text (may contain **bold**)


@dataclass
class Edits:
    rewrites: dict[str, str] = field(default_factory=dict)            # bullet id → new plain text
    drops: set[str] = field(default_factory=set)                      # bullet ids
    adds: dict[str, list[NewBullet]] = field(default_factory=dict)    # entry id → bullets appended
    orders: dict[str, list[str]] = field(default_factory=dict)        # entry id → bullet ids, desired order
    skills: dict[str, list[str]] = field(default_factory=dict)        # skill line id → items

    def touches(self, entry: Entry) -> bool:
        ids = [b.id for b in entry.bullets]
        return (
            any(i in self.rewrites or i in self.drops for i in ids)
            or bool(self.adds.get(entry.id))
            or (entry.id in self.orders and _ordered(ids, self.orders[entry.id]) != ids)
        )


def _ordered(ids: list[str], wanted: list[str]) -> list[str]:
    """`ids` sorted by position in `wanted`; ids not mentioned keep their relative order at the end."""
    rank = {bid: k for k, bid in enumerate(wanted)}
    return sorted(ids, key=lambda bid: (rank.get(bid, len(wanted)), ids.index(bid)))


def _validate(doc: ResumeDoc, edits: Edits) -> None:
    bullet_ids = {b.id for b in doc.bullets()}
    entry_ids = {e.id for e in doc.entries()}
    line_ids = {s.id for s in doc.skill_lines()}
    for bid in [*edits.rewrites, *edits.drops]:
        if bid not in bullet_ids:
            raise EditError(f"unknown bullet id: {bid}")
    for eid in [*edits.adds, *edits.orders]:
        if eid not in entry_ids:
            raise EditError(f"unknown entry id: {eid}")
    for lid in edits.skills:
        if lid not in line_ids:
            raise EditError(f"unknown skill line id: {lid}")
    for eid, new in edits.adds.items():
        if new and not doc.entry(eid).bullets:
            raise EditError(f"entry {eid} has no bullet list to add to")


def _render_entry(doc: ResumeDoc, entry: Entry, edits: Edits) -> str:
    src = doc.source
    units: dict[str, str] = {}
    for b in entry.bullets:
        if b.id in edits.drops:
            continue
        start, end = b.unit_span
        unit = src[start:end]
        if b.id in edits.rewrites:
            cs, ce = b.content_span[0] - start, b.content_span[1] - start
            unit = unit[:cs] + to_latex(edits.rewrites[b.id]) + unit[ce:]
        units[b.id] = unit

    last = entry.bullets[-1]
    line = src[src.rfind("\n", 0, last.content_span[0]) + 1 : last.content_span[0]]
    indent = line[: len(line) - len(line.lstrip(" \t"))]
    for nb in edits.adds.get(entry.id, []):
        body = to_latex(nb.text)
        units[nb.id] = f"{indent}\\item {body}\n" if last.macro == "item" else f"{indent}\\{last.macro}{{{body}}}\n"

    if not units:
        raise EditError(f"edits would leave entry {entry.id} with no bullets")

    order = _ordered(list(units), edits.orders.get(entry.id, []))
    region_end_newline = src[last.unit_span[1] - 1] == "\n"
    text = "".join(u if u.endswith("\n") else u + "\n" for u in (units[k] for k in order))
    return text if region_end_newline else text.rstrip("\n")


def render(doc: ResumeDoc, edits: Edits | None = None) -> str:
    """Return the .tex source with `edits` applied. No edits → the original, byte-for-byte."""
    edits = edits or Edits()
    _validate(doc, edits)

    replacements: list[tuple[int, int, str]] = []
    for entry in doc.entries():
        if entry.bullets and edits.touches(entry):
            start, end = entry.bullets[0].unit_span[0], entry.bullets[-1].unit_span[1]
            replacements.append((start, end, _render_entry(doc, entry, edits)))
    for line in doc.skill_lines():
        if line.id in edits.skills and edits.skills[line.id] != line.items:
            replacements.append((*line.items_span, ", ".join(to_latex(x) for x in edits.skills[line.id])))

    out = doc.source
    for start, end, text in sorted(replacements, reverse=True):
        out = out[:start] + text + out[end:]
    return out
