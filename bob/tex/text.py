"""Convert between LaTeX snippets and plain text.

The LLM only ever sees and writes plain text. `to_plain` is used when reading the
resume; `to_latex` when writing a new bullet back. `**bold**` in plain text becomes
`\\textbf{bold}` so the LLM can keep keyword bolding without writing LaTeX.
"""

import re

_SPECIALS = "&%$#_{}"
# Commands whose brace argument is layout, not text.
_DROP_ARG = {"vspace", "hspace", "vspace*", "hspace*", "label", "ref"}
_WORDS = {
    "textbackslash": "\\",
    "textasciitilde": "~",
    "textasciicircum": "^",
    "ldots": "...",
    "dots": "...",
    "LaTeX": "LaTeX",
    "TeX": "TeX",
}


def mask_comments(src: str) -> str:
    """Return `src` with every comment (unescaped % to end of line) blanked to spaces.

    Offsets are preserved, so positions found in the mask are valid in `src`.
    """
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == "%":
            while i < n and src[i] != "\n":
                out[i] = " "
                i += 1
            continue
        i += 1
    return "".join(out)


def match_brace(src: str, open_idx: int) -> int:
    """Index of the `}` matching the `{` at `open_idx` (escapes respected)."""
    depth = 0
    i = open_idx
    while i < len(src):
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"unbalanced brace opened at offset {open_idx}")


def to_plain(latex: str) -> str:
    """Strip LaTeX markup from a snippet, keeping the human-readable text."""
    s = mask_comments(latex)
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt in _SPECIALS:
                out.append(nxt)
                i += 2
            elif nxt == "\\":
                out.append(" ")
                i += 2
            elif nxt.isalpha():
                j = i + 1
                while j < n and s[j].isalpha():
                    j += 1
                if j < n and s[j] == "*":
                    j += 1
                name = s[i + 1 : j]
                if name in _WORDS:
                    out.append(_WORDS[name])
                    if s.startswith("{}", j):
                        j += 2
                elif name == "href" and s.startswith("{", j):
                    j = match_brace(s, j) + 1  # drop the URL, keep the link text
                elif name in _DROP_ARG and s.startswith("{", j):
                    j = match_brace(s, j) + 1
                i = j
            else:
                i += 2  # \, \; \! etc. — spacing
        elif c in "{}$":
            i += 1
        elif c == "~":
            out.append(" ")
            i += 1
        else:
            out.append(c)
            i += 1
    text = "".join(out)
    text = text.replace("---", "—").replace("--", "–")
    return re.sub(r"\s+", " ", text).strip()


def _escape(text: str) -> str:
    out = []
    for c in text:
        if c == "\\":
            out.append(r"\textbackslash{}")
        elif c in _SPECIALS:
            out.append("\\" + c)
        elif c == "~":
            out.append(r"\textasciitilde{}")
        elif c == "^":
            out.append(r"\textasciicircum{}")
        elif c == "—":
            out.append("---")
        elif c == "–":
            out.append("--")
        else:
            out.append(c)
    return "".join(out)


def to_latex(text: str) -> str:
    """Turn plain text (optionally with **bold**) into a safe LaTeX snippet."""
    text = re.sub(r"\s+", " ", text).strip()
    parts = text.split("**")
    if len(parts) % 2 == 0:  # unbalanced ** — treat literally
        return _escape(text)
    return "".join(
        _escape(p) if k % 2 == 0 else r"\textbf{" + _escape(p) + "}" for k, p in enumerate(parts)
    )


def strip_markers(text: str) -> str:
    """Plain text without **bold** markers — what the verifier compares."""
    return text.replace("**", "")
