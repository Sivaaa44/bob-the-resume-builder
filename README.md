<div align="center">

# 🛠️ Bob the Resume Builder

**Tailor your LaTeX resume to any job. Without making stuff up.**

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
cp .env.example .env              # add your API key
```

You also need LaTeX installed: [TeX Live](https://tug.org/texlive/), [MiKTeX](https://miktex.org/) or [tectonic](https://tectonic-typesetting.github.io/).

**Set up your workspace**

```bash
bob init path/to/resume.tex       # every bullet becomes a fact
bob outline workspace/resume.tex  # check that Bob read your resume correctly
```

Then open `workspace/profile.yaml` and add the things that didn't fit on the page:

```yaml
  - text: Indexed 2M Jira tickets in Pinecone for semantic search
    skills: [Pinecone, vector databases, RAG]
```

**Run it**

```bash
uvicorn bob.api:app --reload                  # backend → :8000
cd frontend && npm install && npm run dev     # UI → http://localhost:5173
```

Or skip the UI:

```bash
bob tailor jd.txt        # analyze + propose changes
bob review <run-id>      # accept / reject / edit
bob finalize <run-id>    # build the PDF
```

## LLM setup

Bob works with any OpenAI-compatible API. Set these in `.env`:

| Provider | `BOB_LLM_BASE_URL` | `BOB_LLM_MODEL` |
|---|---|---|
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash` |
| Groq | `https://api.groq.com/openai/v1` | `openai/gpt-oss-20b` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Ollama | `http://localhost:11434/v1` | `llama3.1` |

…plus `BOB_LLM_API_KEY`. One run uses about 7k tokens.

## Project layout

```
bob/
├── tex/        LaTeX ⇄ structure (parser + editor)
├── profile/    your facts (profile.yaml)
├── tailor/     analyze → match → plan → verify
├── build/      compile + fit to one page
├── llm/        provider client
├── pipeline.py the whole flow
├── cli.py      `bob` command
└── api.py      HTTP API for the UI
frontend/       React + Vite
workspace/      your data (git-ignored)
```

## Tests

```bash
pytest
```

## Roadmap

- [ ] Resume upload + facts editor in the browser
- [ ] `bob serve`: one command, no Node needed
- [ ] Pull job descriptions from LinkedIn and Greenhouse in one click
- [ ] Cover letters from the same verified facts
- [ ] Application tracker

---

<div align="center">
<sub>Built because editing <code>.tex</code> for every application got old.</sub>
</div>
