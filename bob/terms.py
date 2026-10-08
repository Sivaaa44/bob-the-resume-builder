"""Finding skill/keyword terms in text — shared by profile seeding, matching and verification.

Matching is case-insensitive, respects word boundaries (so "Go" doesn't match "Google",
"Java" doesn't match "JavaScript") and tolerates a plural "s"/"es".
"""

import re
from functools import lru_cache


@lru_cache(maxsize=4096)
def _pattern(term: str) -> re.Pattern[str]:
    words = [re.escape(w) for w in term.strip().split()]
    body = r"[\s\-]+".join(words)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?:e?s)?(?![A-Za-z0-9+#])", re.IGNORECASE)


def contains_term(text: str, term: str) -> bool:
    return bool(term.strip()) and bool(_pattern(term).search(text))


def find_terms(text: str, vocabulary: list[str] | set[str]) -> list[str]:
    """Terms from `vocabulary` that occur in `text`. Longer terms win over terms they contain
    ("Adobe Sign API" suppresses a bare "API" found only inside it)."""
    found: list[str] = []
    spans: list[tuple[int, int]] = []
    for term in sorted({t for t in vocabulary if t.strip()}, key=len, reverse=True):
        hits = [m.span() for m in _pattern(term).finditer(text)]
        free = [h for h in hits if not any(s <= h[0] and h[1] <= e for s, e in spans)]
        if free:
            found.append(term)
            spans.extend(free)
    return found


def norm(term: str) -> str:
    return re.sub(r"\s+", " ", term.strip().lower())
