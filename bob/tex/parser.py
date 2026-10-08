"""Parse a resume .tex into a ResumeDoc.

Supported out of the box (Jake's Resume and most of its forks):
  \\section{...}                                  → Section
  \\resumeSubheading{4 args}, \\resumeProjectHeading{2}, \\resumeSubSubheading{2}  → Entry
  \\resumeItem{...}, \\resumeSubItem{...}          → Bullet
  plain \\item ... inside itemize                  → Bullet
  \\textbf{Category}{: a, b, c}                    → SkillLine (a section with these is a skills section)

Other templates can register their macro names via `ParserConfig`.
"""

import re
from dataclasses import dataclass, field

from bob.tex.model import Bullet, Entry, ResumeDoc, Section, SkillLine, Span
from bob.tex.text import mask_comments, match_brace, to_plain


@dataclass
class ParserConfig:
    # macro name → number of brace arguments
    heading_macros: dict[str, int] = field(
        default_factory=lambda: {"resumeSubheading": 4, "resumeProjectHeading": 2, "resumeSubSubheading": 2}
    )
    bullet_macros: set[str] = field(default_factory=lambda: {"resumeItem", "resumeSubItem"})
    # which heading argument holds the subtitle (company / degree); the title is always arg 0
    subtitle_arg: dict[str, int] = field(default_factory=lambda: {"resumeSubheading": 2})


class ParseError(ValueError):
    pass


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "x"


def _unique(slug: str, taken: set[str]) -> str:
    candidate, k = slug, 2
    while candidate in taken:
        candidate = f"{slug}-{k}"
        k += 1
    taken.add(candidate)
    return candidate


def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i].isspace():
        i += 1
    return i


def _read_groups(masked: str, i: int, count: int) -> tuple[list[Span], int]:
    """Read `count` brace groups starting at/after `i`. Returns inner spans and end offset."""
    spans = []
    for _ in range(count):
        i = _skip_ws(masked, i)
        if i >= len(masked) or masked[i] != "{":
            raise ParseError(f"expected '{{' at offset {i}")
        close = match_brace(masked, i)
        spans.append((i + 1, close))
        i = close + 1
    return spans, i


def _line_start(masked: str, pos: int) -> int:
    """Start of pos's line if only whitespace precedes pos on it, else pos."""
    j = pos
    while j > 0 and masked[j - 1] in " \t":
        j -= 1
    return j if j == 0 or masked[j - 1] == "\n" else pos


def _line_end(masked: str, pos: int) -> int:
    """Past the newline if only whitespace (or a comment) follows pos on its line, else pos."""
    j = pos
    while j < len(masked) and masked[j] in " \t":
        j += 1
    if j < len(masked) and masked[j] == "\n":
        return j + 1
    return j if j == len(masked) else pos


_SECTION_RE = re.compile(r"\\section\*?(?![A-Za-z])")
_SKILL_RE = re.compile(r"\\textbf\s*\{")
_ITEM_STOP_RE = re.compile(r"\\item(?![A-Za-z])|\\end\{itemize\}|\\begin\{itemize\}|\\end\{document\}")


def parse(source: str, config: ParserConfig | None = None) -> ResumeDoc:
    config = config or ParserConfig()
    masked = mask_comments(source)

    begin = masked.find(r"\begin{document}")
    end = masked.find(r"\end{document}")
    if begin < 0 or end < 0:
        raise ParseError(r"missing \begin{document} or \end{document}")

    section_marks = [m for m in _SECTION_RE.finditer(masked, begin, end)]
    if not section_marks:
        raise ParseError(r"no \section{...} found")

    sections: list[Section] = []
    taken_sections: set[str] = set()
    for k, m in enumerate(section_marks):
        (title_span,), body_start = _read_groups(masked, m.end(), 1)
        body_end = section_marks[k + 1].start() if k + 1 < len(section_marks) else end
        title = to_plain(source[title_span[0] : title_span[1]])
        section = Section(id=_unique(slugify(title), taken_sections), title=title)
        skill_lines = _parse_skill_lines(source, masked, body_start, body_end, section)
        if skill_lines:
            section.skill_lines = skill_lines
        else:
            section.entries = _parse_entries(source, masked, body_start, body_end, section, config)
        sections.append(section)

    return ResumeDoc(source=source, sections=sections)


def _parse_skill_lines(source: str, masked: str, start: int, end: int, section: Section) -> list[SkillLine]:
    lines: list[SkillLine] = []
    taken: set[str] = set()
    for m in _SKILL_RE.finditer(masked, start, end):
        cat_open = m.end() - 1
        cat_close = match_brace(masked, cat_open)
        i = _skip_ws(masked, cat_close + 1)
        if i >= end or masked[i] != "{":
            continue
        group_close = match_brace(masked, i)
        j = _skip_ws(masked, i + 1)
        if masked[j] != ":":
            continue
        items_start = _skip_ws(masked, j + 1)
        items_end = group_close
        while items_end > items_start and masked[items_end - 1].isspace():
            items_end -= 1
        category = to_plain(source[cat_open + 1 : cat_close])
        raw = source[items_start:items_end]
        items = [to_plain(x) for x in _split_top_level(raw)]
        lines.append(
            SkillLine(
                id=f"{section.id}.{_unique(slugify(category), taken)}",
                section_id=section.id,
                category=category,
                items=[x for x in items if x],
                items_span=(items_start, items_end),
            )
        )
    return lines


def _split_top_level(raw: str) -> list[str]:
    parts, depth, cur, i = [], 0, [], 0
    while i < len(raw):
        c = raw[i]
        if c == "\\" and i + 1 < len(raw):
            cur.append(raw[i : i + 2])
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if c == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    parts.append("".join(cur))
    return parts


def _parse_entries(
    source: str, masked: str, start: int, end: int, section: Section, config: ParserConfig
) -> list[Entry]:
    names = sorted(set(config.heading_macros) | config.bullet_macros | {"item"}, key=len, reverse=True)
    token_re = re.compile(r"\\(" + "|".join(map(re.escape, names)) + r")(?![A-Za-z])")

    entries: list[Entry] = []
    taken: set[str] = set()
    raw_bullets: list[list[tuple[str, Span, Span]]] = []  # per entry: (macro, content_span, macro_span)
    current: Entry | None = None

    i = start
    while True:
        m = token_re.search(masked, i, end)
        if not m:
            break
        name = m.group(1)
        if name in config.heading_macros:
            spans, i = _read_groups(masked, m.end(), config.heading_macros[name])
            title = to_plain(source[spans[0][0] : spans[0][1]]).split("|")[0].strip()
            sub_idx = config.subtitle_arg.get(name)
            subtitle = to_plain(source[spans[sub_idx][0] : spans[sub_idx][1]]) if sub_idx is not None else ""
            slug = slugify(title)
            if slug in taken and subtitle:
                slug = f"{slug}-{slugify(subtitle)}"
            current = Entry(id=f"{section.id}.{_unique(slug, taken)}", section_id=section.id,
                            title=title, subtitle=subtitle)
            entries.append(current)
            raw_bullets.append([])
            continue

        if name in config.bullet_macros:
            (content,), i = _read_groups(masked, m.end(), 1)
            macro_span = (m.start(), i)
        else:  # plain \item: text runs until the next \item / list boundary
            stop = _ITEM_STOP_RE.search(masked, m.end(), end)
            c_end = stop.start() if stop else end
            c_start = _skip_ws(masked, m.end())
            while c_end > c_start and masked[c_end - 1].isspace():
                c_end -= 1
            i = max(c_end, m.end())
            if c_start >= c_end:
                continue  # empty \item
            macro_span = (m.start(), c_end)
            if masked[c_start] == "{" and match_brace(masked, c_start) == c_end - 1:
                c_start, c_end = c_start + 1, c_end - 1  # \item{text}
            content = (c_start, c_end)

        if current is None:
            current = Entry(id=f"{section.id}.{_unique('items', taken)}", section_id=section.id,
                            title=section.title)
            entries.append(current)
            raw_bullets.append([])
        raw_bullets[-1].append((name, content, macro_span))

    for entry, raws in zip(entries, raw_bullets):
        prev_end = None
        for n, (macro, content, (m_start, m_end)) in enumerate(raws, start=1):
            unit_start = prev_end if prev_end is not None else _line_start(masked, m_start)
            unit_end = _line_end(masked, m_end)
            entry.bullets.append(
                Bullet(
                    id=f"{entry.id}.b{n}",
                    entry_id=entry.id,
                    text=to_plain(source[content[0] : content[1]]),
                    macro=macro,
                    content_span=content,
                    unit_span=(unit_start, unit_end),
                )
            )
            prev_end = unit_end
    return entries
