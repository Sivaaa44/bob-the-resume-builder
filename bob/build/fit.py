"""Step 6 — make it fit the page budget by dropping the least relevant bullets.

Deterministic and transparent: it reports exactly what it dropped. It never drops the last
bullet of an entry and never touches spacing or margins.
"""

import copy
from collections.abc import Callable
from dataclasses import dataclass, field

from bob.tex.editor import Edits, ordered, render
from bob.tex.model import ResumeDoc


@dataclass
class FitResult:
    tex: str
    pages: int
    dropped: list[str] = field(default_factory=list)   # bullet ids (existing) or new-bullet ids
    fits: bool = True


def _present(doc: ResumeDoc, edits: Edits) -> dict[str, list[str]]:
    """entry id → ids of bullets currently on the page (existing minus drops, plus adds)."""
    out = {}
    for e in doc.entries():
        ids = [b.id for b in e.bullets if b.id not in edits.drops] + [n.id for n in edits.adds.get(e.id, [])]
        if ids:
            out[e.id] = ordered(ids, edits.orders.get(e.id, []))  # page order
    return out


def fit(
    doc: ResumeDoc,
    edits: Edits,
    scores: dict[str, float],
    measure: Callable[[str], int],
    max_pages: int = 1,
    max_drops: int = 8,
) -> FitResult:
    edits = copy.deepcopy(edits)
    entry_order = [e.id for e in doc.entries()]
    tex = render(doc, edits)
    pages = measure(tex)
    dropped: list[str] = []

    while pages > max_pages and len(dropped) < max_drops:
        present = _present(doc, edits)
        candidates = [
            (scores.get(bid, 0.0), -entry_order.index(eid), -pos, bid, eid)
            for eid, ids in present.items() if len(ids) > 1
            for pos, bid in enumerate(ids)
        ]
        if not candidates:
            break
        # lowest score; ties → entries further down the page, then the last bullet in the entry
        _, _, _, bid, eid = min(candidates)
        added = [n for n in edits.adds.get(eid, []) if n.id == bid]
        if added:
            edits.adds[eid].remove(added[0])
        else:
            edits.drops.add(bid)
        dropped.append(bid)
        tex = render(doc, edits)
        pages = measure(tex)

    return FitResult(tex=tex, pages=pages, dropped=dropped, fits=pages <= max_pages)
