"""A run = one job application. Stored as workspace/runs/<id>/run.json, next to its outputs."""

import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from bob.llm.base import Usage
from bob.tailor.models import Coverage, JobAnalysis, Proposal

RunStatus = Literal["awaiting_review", "finalized", "aborted"]


class DroppedBullet(BaseModel):
    id: str
    text: str


class BuildResult(BaseModel):
    pages: int
    fits: bool
    dropped: list[DroppedBullet] = Field(default_factory=list)
    skills_added: list[str] = Field(default_factory=list)
    tex_path: str
    pdf_path: str


class Run(BaseModel):
    id: str
    created_at: str
    status: RunStatus = "awaiting_review"
    jd_text: str
    resume_sha: str                       # base resume fingerprint; ids are only valid for this version
    analysis: JobAnalysis
    coverage: list[Coverage]
    proposals: list[Proposal]
    skills_added: list[str] = Field(default_factory=list)   # preview: profile skills the JD asks for
    include_skill_additions: bool = True
    result: BuildResult | None = None
    token_usage: dict[str, Usage] = Field(default_factory=dict)   # step name → tokens used

    def record_usage(self, step: str, used: Usage) -> None:
        if used.calls:
            self.token_usage[step] = self.token_usage.get(step, Usage()).add(used)

    @property
    def total_usage(self) -> Usage:
        total = Usage()
        for u in self.token_usage.values():
            total = total.add(u)
        return total

    def proposal(self, proposal_id: str) -> Proposal:
        for p in self.proposals:
            if p.id == proposal_id:
                return p
        raise KeyError(f"unknown proposal id: {proposal_id}")


class RunStore:
    def __init__(self, runs_dir: Path):
        self.dir = Path(runs_dir)

    def new_id(self, analysis: JobAnalysis) -> str:
        label = re.sub(r"[^a-z0-9]+", "-", f"{analysis.company} {analysis.title}".lower()).strip("-")[:40]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
        return "-".join(x for x in (stamp, label, secrets.token_hex(2)) if x)

    def run_dir(self, run_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9-]+", run_id):
            raise KeyError(f"invalid run id: {run_id}")
        return self.dir / run_id

    def save(self, run: Run) -> None:
        d = self.run_dir(run.id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "run.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")

    def load(self, run_id: str) -> Run:
        path = self.run_dir(run_id) / "run.json"
        if not path.exists():
            raise KeyError(f"no run with id {run_id}")
        return Run.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[Run]:
        if not self.dir.exists():
            return []
        runs = [Run.model_validate_json(p.read_text(encoding="utf-8")) for p in self.dir.glob("*/run.json")]
        return sorted(runs, key=lambda r: r.created_at, reverse=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
