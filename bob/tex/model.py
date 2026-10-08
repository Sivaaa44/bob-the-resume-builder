"""Structured view of a resume .tex file.

Every editable piece keeps the character span it came from in `ResumeDoc.source`,
so the editor can splice changes in without touching anything else.
"""

from pydantic import BaseModel

Span = tuple[int, int]  # [start, end) offsets into ResumeDoc.source


class Bullet(BaseModel):
    id: str              # "experience.data-engineering-intern.b1"
    entry_id: str
    text: str            # plain text, LaTeX stripped — what the LLM and the verifier see
    macro: str           # "resumeItem", "item", ...
    content_span: Span   # the bullet's text inside the source
    unit_span: Span      # the whole line(s) for this bullet, incl. leading comments/blank lines


class Entry(BaseModel):
    id: str              # "experience.data-engineering-intern"
    section_id: str
    title: str
    subtitle: str = ""
    bullets: list[Bullet] = []


class SkillLine(BaseModel):
    id: str              # "technical-skills.languages"
    section_id: str
    category: str
    items: list[str]
    items_span: Span     # "Python, SQL, ..." part of `\textbf{Languages}{: Python, SQL, ...}`


class Section(BaseModel):
    id: str              # "experience"
    title: str
    entries: list[Entry] = []
    skill_lines: list[SkillLine] = []


class ResumeDoc(BaseModel):
    source: str
    sections: list[Section]

    def entries(self) -> list[Entry]:
        return [e for s in self.sections for e in s.entries]

    def bullets(self) -> list[Bullet]:
        return [b for e in self.entries() for b in e.bullets]

    def skill_lines(self) -> list[SkillLine]:
        return [line for s in self.sections for line in s.skill_lines]

    def entry(self, entry_id: str) -> Entry:
        for e in self.entries():
            if e.id == entry_id:
                return e
        raise KeyError(f"unknown entry id: {entry_id}")

    def bullet(self, bullet_id: str) -> Bullet:
        for b in self.bullets():
            if b.id == bullet_id:
                return b
        raise KeyError(f"unknown bullet id: {bullet_id}")

    def skill_line(self, line_id: str) -> SkillLine:
        for line in self.skill_lines():
            if line.id == line_id:
                return line
        raise KeyError(f"unknown skill line id: {line_id}")
