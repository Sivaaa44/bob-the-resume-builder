"""The user's truth: facts about their work, and the skills they can honestly claim."""

from typing import Literal

from pydantic import BaseModel, Field


class Fact(BaseModel):
    id: str
    text: str                                  # a true statement, in plain English
    entry: str | None = None                   # resume entry this belongs to; None = general fact
    skills: list[str] = Field(default_factory=list)  # tools/skills/terms this fact evidences (aliases welcome)
    source: Literal["resume", "user"] = "user"


class Profile(BaseModel):
    facts: list[Fact] = Field(default_factory=list)
    skills: dict[str, list[str]] = Field(default_factory=dict)  # category → skills, e.g. {"Languages": [...]}

    def fact(self, fact_id: str) -> Fact:
        for f in self.facts:
            if f.id == fact_id:
                return f
        raise KeyError(f"unknown fact id: {fact_id}")

    def fact_ids(self) -> set[str]:
        return {f.id for f in self.facts}

    def all_skills(self) -> list[str]:
        """Every skill term the user has evidence for (skills lists + fact skills), de-duplicated."""
        seen: dict[str, str] = {}
        for items in self.skills.values():
            for s in items:
                seen.setdefault(s.lower(), s)
        for f in self.facts:
            for s in f.skills:
                seen.setdefault(s.lower(), s)
        return list(seen.values())
