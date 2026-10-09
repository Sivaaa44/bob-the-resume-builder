# CLAUDE.md

Bob tailors a LaTeX resume to a job description **without inventing anything**. The user keeps one
base `.tex` and a `profile.yaml` of true facts; for each JD, Bob proposes small per-bullet changes,
verifies each against the facts it cites, the human accepts/edits/rejects, and Bob builds a PDF.
Design and rationale: `specs/03-v2 architecture.md`.

## Non-negotiable design rules

- **The LLM never reads or writes LaTeX.** It sees plain text; `bob/tex/editor.py` splices text into
  parsed spans. Rendering with no edits must stay byte-identical to the input.
- **Every LLM output is validated** (pydantic) and cross-checked against known ids; unknown ids are dropped.
- **The verifier (`bob/tailor/verify.py`) is the product.** Never weaken a check to make a proposal pass.
  New fabrication patterns get a check *and* a test in `tests/test_plan_verify.py`.
- Prefer deterministic code over LLM calls (ordering, fitting, skills, most verification).
- Plain Python, no agent framework. The whole flow is `bob/pipeline.py`; CLI (`bob/cli.py`) and
  API (`bob/api.py`) are thin wrappers over it.

## Layout

```
bob/tex/        parse .tex → ResumeDoc (spans), plain-text conversion, span editor
bob/profile/    Fact/Profile models, profile.yaml store, seeding from a resume
bob/llm/        LLM protocol, OpenAI-compatible client (Groq default), FakeLLM for tests
bob/tailor/     analyze (JD) → match (facts) → plan (proposals) → verify; relevance scoring
bob/build/      compile (pdflatex/xelatex/tectonic) and the page-fit loop
bob/runs.py     Run model, stored as workspace/runs/<id>/run.json
frontend/       React + Vite UI over the API (no UI library; hash routing)
tests/          pytest; fixtures in tests/fixtures (Jake's-Resume-style resume.tex, jd.txt)
```

User data lives in `workspace/` (git-ignored): `resume.tex`, `profile.yaml`, `runs/`.

## Commands

```bash
pip install -e '.[dev]'                 # backend + `bob` CLI
pytest                                  # all tests; TeX compile tests skip if pdflatex is missing
uvicorn bob.api:app --reload            # API on :8000
cd frontend && npm install && npm run dev    # UI on :5173 (proxies /api to :8000)
cd frontend && npx vite build           # check the frontend builds
bob init resume.tex | outline | facts | tailor jd.txt | review <run> | finalize <run> | runs | show <run>
```

LLM config is in `.env` (see `.env.example`): `BOB_LLM_BASE_URL`, `BOB_LLM_API_KEY`, `BOB_LLM_MODEL`.

## Conventions

- Tests never call a real LLM: use `FakeLLM` / `tests.conftest.scripted_llm()` and `httpx.MockTransport`.
- New parser support goes through `ParserConfig` (macro names), with a fixture-based test.
- Match the existing style: small modules, docstrings that say *why*, no new dependencies without need.
- Commits: author `sivaaa44 <sancarsnow44@gmail.com>`, no `Co-Authored-By` or other AI attribution trailers.
