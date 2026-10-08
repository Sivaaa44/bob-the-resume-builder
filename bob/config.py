"""Settings and workspace paths. Everything is read from env vars (and .env if present)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Workspace:
    """Where one user's data lives: base resume, truth profile, and past runs."""

    root: Path

    @property
    def resume_path(self) -> Path:
        return self.root / "resume.tex"

    @property
    def profile_path(self) -> Path:
        return self.root / "profile.yaml"

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"


@dataclass(frozen=True)
class Settings:
    home: Path = field(default_factory=lambda: Path(os.getenv("BOB_HOME", "./workspace")))
    llm_base_url: str = field(
        default_factory=lambda: os.getenv("BOB_LLM_BASE_URL", "https://api.groq.com/openai/v1")
    )
    llm_api_key: str = field(
        default_factory=lambda: os.getenv("BOB_LLM_API_KEY") or os.getenv("GROQ_API_KEY", "")
    )
    llm_model: str = field(default_factory=lambda: os.getenv("BOB_LLM_MODEL", "llama-3.3-70b-versatile"))
    max_pages: int = field(default_factory=lambda: int(os.getenv("BOB_MAX_PAGES", "1")))

    @property
    def workspace(self) -> Workspace:
        return Workspace(self.home)
