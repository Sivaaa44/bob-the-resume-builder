"""Compile LaTeX to PDF and count pages.

Engine choice (override with BOB_TEX_ENGINE=pdflatex|xelatex|lualatex|tectonic):
  resumes using fontspec → xelatex (or tectonic); otherwise pdflatex (or tectonic).
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


class CompileError(RuntimeError):
    def __init__(self, message: str, log: str = ""):
        super().__init__(message)
        self.log = log


@dataclass
class CompileResult:
    pdf_path: Path
    pages: int
    log: str


def choose_engine(tex: str) -> str:
    forced = os.getenv("BOB_TEX_ENGINE")
    if forced:
        if not shutil.which(forced):
            raise CompileError(f"BOB_TEX_ENGINE={forced} is not installed")
        return forced
    preferred = ["xelatex", "lualatex"] if "fontspec" in tex else ["pdflatex"]
    for engine in [*preferred, "tectonic"]:
        if shutil.which(engine):
            return engine
    raise CompileError("No LaTeX engine found. Install TeX Live (pdflatex) or tectonic.")


def _command(engine: str, tex_file: str) -> list[str]:
    if engine == "tectonic":
        return ["tectonic", "--keep-logs", tex_file]
    return [engine, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", tex_file]


def latex_errors(log: str, limit: int = 3) -> str:
    """The first few LaTeX error lines, readable without the whole log."""
    lines = log.splitlines()
    picked = []
    for i, line in enumerate(lines):
        if line.startswith("!") or ": error:" in line or (".tex:" in line and "Error" in line):
            picked.append("\n".join(lines[i : i + 3]))
            if len(picked) == limit:
                break
    return "\n".join(picked) or log[-1500:]


def page_count(pdf: Path) -> int:
    return len(PdfReader(pdf).pages)


def compile_tex(tex: str, workdir: Path, name: str = "resume", search_dirs: list[Path] = ()) -> CompileResult:
    """Write `<name>.tex` into workdir and compile it there. `search_dirs` are added to TEXINPUTS so
    local .cls/.sty/images next to the base resume are found."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    tex_file = workdir / f"{name}.tex"
    tex_file.write_text(tex, encoding="utf-8")
    pdf = workdir / f"{name}.pdf"
    pdf.unlink(missing_ok=True)

    engine = choose_engine(tex)
    env = dict(os.environ)
    if search_dirs:
        env["TEXINPUTS"] = os.pathsep.join(str(Path(d).resolve()) for d in search_dirs) + os.pathsep
    try:
        res = subprocess.run(_command(engine, tex_file.name), cwd=workdir, env=env,
                             capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired as e:
        raise CompileError(f"{engine} timed out") from e
    log = res.stdout + res.stderr
    if res.returncode != 0 or not pdf.exists():
        raise CompileError(f"{engine} failed:\n{latex_errors(log)}", log)
    return CompileResult(pdf_path=pdf, pages=page_count(pdf), log=log)
