"""Data passed between the tailoring steps (and stored in a run)."""

from typing import Literal

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    id: str                                   # "r1"
    text: str
    importance: Literal["must", "nice"]
    keywords: list[str] = Field(default_factory=list)  # exact phrases an ATS would scan for


class JobAnalysis(BaseModel):
    title: str = ""
    company: str = ""
    requirements: list[Requirement]

    def requirement(self, req_id: str) -> Requirement:
        for r in self.requirements:
            if r.id == req_id:
                return r
        raise KeyError(f"unknown requirement id: {req_id}")


class Coverage(BaseModel):
    requirement_id: str
    strength: Literal["direct", "adjacent", "none"]
    fact_ids: list[str] = Field(default_factory=list)
    note: str = ""
    literal: bool = False   # True if a keyword literally appears in a cited fact (not just LLM judgement)


class Check(BaseModel):
    name: str
    level: Literal["error", "warning"]
    message: str


ProposalStatus = Literal["blocked", "pending", "accepted", "edited", "rejected"]


class Proposal(BaseModel):
    id: str                                   # "p1"
    kind: Literal["rewrite", "add"]
    entry_id: str
    bullet_id: str | None = None              # set for rewrites
    original_text: str = ""                   # empty for adds
    new_text: str
    fact_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    checks: list[Check] = Field(default_factory=list)
    status: ProposalStatus = "pending"
    user_text: str | None = None              # set when the human edits the proposal

    @property
    def final_text(self) -> str:
        return self.user_text if self.status == "edited" and self.user_text else self.new_text

    @property
    def errors(self) -> list[Check]:
        return [c for c in self.checks if c.level == "error"]
