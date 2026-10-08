"""Finding skill/keyword terms in text — shared by profile seeding, matching and verification.

Matching is case-insensitive, respects word boundaries (so "Go" doesn't match "Google",
"Java" doesn't match "JavaScript") and tolerates a plural "s"/"es".
"""

import re
from functools import lru_cache


@lru_cache(maxsize=4096)
def _pattern(term: str) -> re.Pattern[str]:
    words = term.strip().split()
    last = words[-1]
    if len(last) >= 4 and last.endswith("s") and last[-2].islower():
        words[-1] = last[:-1]  # "databases" also matches "database"
    body = r"[\s\-]+".join(re.escape(w) for w in words)
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


def same_term(a: str, b: str) -> bool:
    """True if a and b name the same thing (case, spacing, hyphens and plurals aside)."""
    return contains_term(a, b) and contains_term(b, a)


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[.+#/-]*[A-Za-z0-9+#]+)*[+#]*")


def name_like_tokens(text: str) -> list[str]:
    """Tokens that look like tools, products or names: "AWS", "PostgreSQL", "Node.js", "C++",
    or a capitalized word mid-sentence. Used to catch terms no vocabulary knows about."""
    out = []
    for k, m in enumerate(_TOKEN_RE.finditer(text)):
        tok = m.group(0)
        if m.start() > 0 and text[m.start() - 1].isdigit():
            continue  # unit glued to a number: "2M+", "40k", "3x"
        sentence_start = k == 0 or text[: m.start()].rstrip().endswith((".", ":", ";", "!", "?"))
        if (
            any(c.isupper() for c in tok[1:])
            or any(c.isdigit() or c in ".+#" for c in tok)
            or (tok[0].isupper() and not sentence_start)
        ):
            out.append(tok.rstrip("."))
    return list(dict.fromkeys(out))


def norm(term: str) -> str:
    return re.sub(r"\s+", " ", term.strip().lower())
