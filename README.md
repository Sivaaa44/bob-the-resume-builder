<div align="center">

# 🛠️ Bob the Resume Builder

**Tailor your LaTeX resume to any job. Without making stuff up.**

[![CI](https://github.com/Sivaaa44/bob-the-resume-builder/actions/workflows/ci.yml/badge.svg)](https://github.com/Sivaaa44/bob-the-resume-builder/actions/workflows/ci.yml)

Paste a job description → review the changes → get a one-page PDF.
No TeX editor. No hallucinated skills.

</div>

---

## Why Bob

Asking a chatbot to "rewrite my resume for this job" works, until it quietly adds Kubernetes to a project that never touched it.

Bob does it differently:

- 🔒 **Every change cites a fact.** Your facts live in `profile.yaml`. A bullet with a claim that no fact backs up gets blocked.
- 🧩 **Your template stays intact.** The AI only ever sees plain sentences. Bob puts them back into your `.tex` itself.
- ✅ **You decide.** Each change is a card: accept, reject, edit, or try again.
- 📄 **Always one page.** If the resume runs over, Bob cuts the least relevant bullets and tells you which ones.

## How it works

```
 your resume.tex ──► bob init ──► profile.yaml (your facts)
                                        │
 job description ──► analyze ──► match ──► plan ──► verify ──► you review ──► PDF
                       (AI)       (AI)     (AI)    (code)
```

## Quick start

```bash
git clone https://github.com/Sivaaa44/bob-the-resume-builder
cd bob-the-resume-builder
pip install -e ".[dev]"
```

You also need LaTeX installed: [TeX Live](https://tug.org/texlive/), [MiKTeX](https://miktex.org/) or [tectonic](https://tectonic-typesetting.github.io/).

**Run it**

```bash
uvicorn bob.api:app --reload                  # backend → :8000
cd frontend && npm install && npm run dev     # UI → http://localhost:5173
```

Then, all in the browser:

1. **Upload your `resume.tex`**: Bob shows how it read your resume, and every bullet becomes a fact.
2. **Your facts**: add what didn't fit on the page, plus skill aliases you'd defend in an interview.
3. **Settings**: pick a provider, paste your key, hit *Test connection*.
4. **New application**: paste a JD, review the cards, build the PDF.

<details>
<summary>Prefer the terminal?</summary>

```bash
bob init path/to/resume.tex       # workspace + facts
bob outline workspace/resume.tex  # check the parse
bob tailor jd.txt                 # analyze + propose changes
bob review <run-id>               # accept / reject / edit
bob finalize <run-id>             # build the PDF
```

Keys go in `.env` (see `.env.example`). Anything saved from the Settings page takes priority.
</details>

## LLM setup

Bob works with any OpenAI-compatible API. Set these in `.env`:

| Provider | `BOB_LLM_BASE_URL` | `BOB_LLM_MODEL` |
|---|---|---|
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash` |
| Groq | `https://api.groq.com/openai/v1` | `openai/gpt-oss-20b` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Ollama | `http://localhost:11434/v1` | `llama3.1` |

…plus `BOB_LLM_API_KEY`, or set all of it on the Settings page. One run uses about 7–15k tokens.

## Project layout

```
bob/
├── tex/        LaTeX ⇄ structure (parser + editor)
├── profile/    your facts (profile.yaml)
├── tailor/     analyze → match → plan → verify
├── build/      compile + fit to one page
├── llm/        provider client
├── setup.py    import a resume, sanity-check the parse
├── pipeline.py the whole flow
├── cli.py      `bob` command
└── api.py      HTTP API for the UI
frontend/       React + Vite
evals/          verifier corpus + live eval harness
workspace/      your data (git-ignored)
```

## Tests & evals

```bash
pytest                 # unit tests + the verifier corpus (no API key needed)
python -m evals.run    # live eval with your model: coverage, leaks, tokens
```

`evals/verifier_corpus.yaml` is a labelled set of honest and fabricated rewrites. CI fails if a single
fabrication slips through. See [`evals/README.md`](evals/README.md).

## Roadmap

- [x] Resume upload + facts editor in the browser
- [x] Eval set + CI
- [ ] `bob serve`: one command, no Node needed
- [ ] Pull job descriptions from LinkedIn and Greenhouse in one click
- [ ] Cover letters from the same verified facts
- [ ] Application tracker

---

<div align="center">
<sub>Built because editing <code>.tex</code> for every application got old.</sub>
</div>
