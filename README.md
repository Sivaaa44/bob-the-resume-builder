# Bob the Resume Builder

Tailor your LaTeX resume to a job description without making anything up.

You give Bob your resume `.tex` once, plus the true facts about your work. For each job, paste
the JD: Bob proposes small, per-bullet changes that use the JD's wording, checks every one
against the facts it cites, and you accept, edit or reject each change. Bob then builds a
one-page PDF. You never open a TeX editor.

**Why not just ask a chatbot?** A chat rewrites the whole file and you have to reread every line
to make sure it didn't invent a tool or a number. Bob never lets the model touch LaTeX, and a
checker blocks any claim your facts don't support. See `specs/03-v2 architecture.md`.

## Setup

```bash
pip install -e '.[dev]'
cp .env.example .env          # set BOB_LLM_API_KEY (Groq by default; any OpenAI-compatible API works)
```

You also need a LaTeX engine: TeX Live (`pdflatex`) or `tectonic`.

## Use it from the terminal

```bash
bob init path/to/resume.tex   # creates workspace/ with resume.tex and profile.yaml
# edit workspace/profile.yaml: add facts that didn't fit on the page and skill aliases
bob tailor jd.txt             # coverage report + verified proposals
bob review <run-id>           # accept / reject / edit / regenerate, one by one
bob finalize <run-id>         # builds workspace/runs/<run-id>/tailored.pdf
bob runs                      # your application history
```

## Or run the web app

```bash
uvicorn bob.api:app --reload        # API on :8000
cd frontend && npm install && npm run dev   # UI on :5173
```

## Tests

```bash
pytest
```
