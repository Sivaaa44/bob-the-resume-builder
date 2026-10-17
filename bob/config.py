"""Settings and workspace paths.

Read from env vars (and .env if present). Values saved from the web UI live in
workspace/settings.json and take precedence, so users never have to edit .env.
"""

import json
import os
from dataclasses import dataclass, field, replace
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

    @property
    def settings_path(self) -> Path:
        return self.root / "settings.json"

    @property
    def ready(self) -> bool:
        return self.resume_path.exists() and self.profile_path.exists()


@dataclass(frozen=True)
class Settings:
    home: Path = field(default_factory=lambda: Path(os.getenv("BOB_HOME", "./workspace")))
    llm_base_url: str = field(
        default_factory=lambda: os.getenv("BOB_LLM_BASE_URL", "https://api.groq.com/openai/v1")
    )
    llm_api_key: str = field(
        default_factory=lambda: os.getenv("BOB_LLM_API_KEY") or os.getenv("GROQ_API_KEY", "")
    )
    llm_model: str = field(default_factory=lambda: os.getenv("BOB_LLM_MODEL", "openai/gpt-oss-20b"))
    max_pages: int = field(default_factory=lambda: int(os.getenv("BOB_MAX_PAGES", "1")))

    @property
    def workspace(self) -> Workspace:
        return Workspace(self.home)

    @property
    def has_llm_key(self) -> bool:
        local = any(h in self.llm_base_url for h in ("localhost", "127.0.0.1"))
        return bool(self.llm_api_key) or local

    @classmethod
    def load(cls, home: Path | str | None = None) -> "Settings":
        """Env/.env settings, overridden by whatever the UI saved in <home>/settings.json."""
        base = cls() if home is None else cls(home=Path(home))
        try:
            saved = json.loads(base.workspace.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return base
        updates = {k: saved[k] for k in UI_FIELDS if saved.get(k) not in (None, "")}
        if "max_pages" in updates:
            updates["max_pages"] = int(updates["max_pages"])
        return replace(base, **updates)


UI_FIELDS = ("llm_base_url", "llm_api_key", "llm_model", "max_pages")


def save_settings(ws: Workspace, **values) -> None:
    """Merge values into workspace/settings.json (the API key stays on this machine)."""
    ws.root.mkdir(parents=True, exist_ok=True)
    try:
        current = json.loads(ws.settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        current = {}
    # None or "" means "leave as is", so saving the form without retyping the key keeps it
    current.update({k: v for k, v in values.items() if k in UI_FIELDS and v not in (None, "")})
    ws.settings_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    try:
        ws.settings_path.chmod(0o600)  # owner-only: it holds an API key
    except OSError:
        pass
