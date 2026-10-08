# Bob v2 — Backend Architecture & Build Plan

## What the user actually wants

> "I have one resume (.tex) and a set of true facts about my work. For each job I apply to,
> I paste the JD and get back a resume that speaks the JD's language — without lying,
> without opening a TeX editor, and with me approving what changes."

So the product promises three things, in this order:

1. **Truthful.** Every changed line is backed by a fact the user confirmed. The system
   *proves* this with a checker; it does not just ask the LLM nicely.
2. **Zero LaTeX.** The user's template is never broken. The LLM never sees or writes LaTeX —
   it reads and writes plain sentences; our code puts them into the right slots.
3. **Fast human review.** Changes are small, independent proposals (one bullet each) that
   the user accepts / rejects / edits / regenerates individually. Output always compiles and
   fits the page budget.

This is what a chat window can't give you: a chat rewrites the whole file and you reread
every line hoping it didn't invent something.

## Design rules

- **LLM writes sentences, code writes LaTeX.** The `.tex` is parsed into addressable
  slots (bullets, skill lists). Edits are operations on slots, applied by code.
- **Facts are the source of truth, and the resume is the first source of facts.**
  `bob init` turns every existing bullet into a fact automatically. The user then adds
  more facts (things that didn't fit on the page, extra detail, aliases).
- **Every LLM output is validated.** Structured JSON → pydantic models → cross-checked
  against known IDs. Unknown IDs are dropped, never trusted.
- **Deterministic where possible.** Bullet ordering, skill ordering, page fitting and
  most verification are plain code. The LLM is used for three things only: reading the JD,
  judging which facts support which requirement, and phrasing bullets.
- **Plain Python, no agent framework.** The flow is linear with one human checkpoint;
  a run is a JSON file on disk. Easy to read, easy to debug.

## The flow

```
 ONE-TIME                                   PER JOB APPLICATION
 ────────                                   ───────────────────
 bob init resume.tex                        bob tailor jd.txt
   │                                          │
   ├─ parse .tex → ResumeDoc                  ├─ 1. analyze   JD → requirements (must/nice + ATS keywords)   [LLM]
   └─ seed profile.yaml:                      ├─ 2. match     requirement ↔ facts, cited by id             [LLM + code]
        one fact per bullet,                  ├─ 3. plan      proposals: rewrite bullet / add bullet        [LLM]
        skills from skills section            ├─ 4. verify    every proposal checked against its evidence   [code (+ optional LLM)]
   user edits profile.yaml                    ├─ 5. review    human: accept / reject / edit / regenerate    [HUMAN]
   (adds facts, aliases, skills)              └─ 6. build     apply → reorder → fit to page → compile PDF   [code]
```

## Package layout

```
bob/
  config.py              settings (env vars) + workspace paths
  tex/
    model.py             ResumeDoc, Section, Entry, Bullet, SkillLine (with source spans)
    text.py              LaTeX ⇄ plain text (escape / unescape / strip formatting)
    parser.py            .tex → ResumeDoc (brace-aware, comment-aware)
    editor.py            ResumeDoc + edits → new .tex (byte-identical when no edits)
  profile/
    model.py             Fact, Profile
    store.py             load/save profile.yaml, seed from a ResumeDoc
  llm/
    base.py              LLM protocol: complete_json(system, user, schema) -> model
    openai_compat.py     Groq / OpenAI / OpenRouter / Ollama (any OpenAI-compatible API)
    fake.py              scripted LLM for tests
  tailor/
    models.py            Requirement, JobAnalysis, Coverage, Proposal, Check
    analyze.py           step 1
    match.py             step 2
    plan.py              step 3
    verify.py            step 4
    relevance.py         deterministic scoring + ordering of bullets and skills
  build/
    compile.py           pdflatex/latexmk/tectonic wrapper → PDF + page count
    fit.py               step 6: drop lowest-relevance bullets until it fits
  runs.py                Run model + RunStore (workspace/runs/<id>/run.json)
  pipeline.py            start_run / decide / regenerate / finalize — the whole flow in one file
  cli.py                 `bob init | outline | tailor | review | finalize | runs`
  api.py                 FastAPI over pipeline.py
tests/                   one test module per package module, fixtures in tests/fixtures/
```

Workspace (user data, git-ignored), default `./workspace`, override with `BOB_HOME`:

```
workspace/
  resume.tex             the base resume (never modified)
  profile.yaml           the truth: facts + skills
  runs/<run_id>/run.json, tailored.tex, tailored.pdf
```

## Core data model

```python
# tex/model.py
Bullet    id="experience.acme.b1", entry_id, text (plain), macro, content_span, unit_span
Entry     id="experience.acme", section_id, title, subtitle, bullets[]
SkillLine id="skills.languages", category, items[], items_span
Section   id="experience", title, entries[], skill_lines[]

# profile/model.py
Fact      id, text, entry (Entry id or None = general), skills[], source ("resume"|"user")
Profile   facts[], skills{category: [items]}

# tailor/models.py
Requirement  id="r1", text, importance must|nice, keywords[]
Coverage     requirement_id, strength direct|adjacent|none, fact_ids[], note
Proposal     id, kind rewrite|add, bullet_id|entry_id, original_text, new_text,
             fact_ids[], requirement_ids[], rationale, checks[], status
Check        name, level error|warning, message
```

Proposal status: `blocked` (failed verification) → never applied. `pending` → awaiting the
human. `accepted` / `edited` → applied at build. `rejected` → not applied.

## The guardrail (step 4) — how "no fabrication" is enforced

For each proposal, **evidence** = original bullet text (for rewrites) + cited facts' text and
skills. Then:

| Check | Level | Rule |
|---|---|---|
| `facts_exist` | error | every cited fact id exists |
| `facts_scope` | error | cited facts belong to this entry (or are general) — can't move one job's work to another |
| `numbers` | error | every number in the new text appears in the evidence |
| `terms` | error | every known skill/JD keyword in the new text appears in the evidence, **or** belongs to a requirement that step 2 marked `direct` using one of the cited facts |
| `length` | warning | new text not much longer than the original (page budget) |
| `entailment` | error | optional LLM judge: "is every claim supported by the evidence?" |

The `terms` rule is what lets the system "swap in JD terminology" honestly: if the JD says
*vector databases* and the matcher found your *Pinecone* fact directly covers it (and showed
you that), a bullet citing that fact may say "vector database". A bullet citing nothing
relevant may not.

## Versions

Each version has a goal, a definition of done, and tests. Don't start the next one until
the current one's tests pass.

### V0 — Clean slate
- Remove the v1 LangGraph code (it stays in git history). Add `pyproject.toml`, package
  skeleton, pytest config, this spec.
- **Done when:** `pytest` runs green on an empty suite; `pip install -e .` gives a `bob` command.

### V1 — LaTeX layer (the foundation)
- Parser for Jake's-Resume-style templates (`\resumeSubheading`, `\resumeProjectHeading`,
  `\resumeItem`) **and** plain `\item` lists; skills lines (`\textbf{Category}{: a, b}`).
- Editor operations: rewrite bullet, drop bullet, add bullet, reorder bullets in an entry,
  set skill-line items.
- **Done when:** parsing the fixture yields the right sections/entries/bullets/skills;
  `render(doc, no edits) == original` byte-for-byte; each edit op produces brace-balanced
  LaTeX that re-parses to the expected structure; special characters (`& % $ # _`) round-trip;
  commented-out lines are ignored. `bob outline resume.tex` prints the structure.

### V2 — Profile (truth facts)
- `Fact` / `Profile` models, YAML store, validation (unique ids, entry ids exist).
- `bob init resume.tex` creates a workspace and seeds one fact per bullet + skills.
- **Done when:** seeding the fixture produces a valid profile whose facts map 1:1 to bullets;
  save → load round-trips; invalid profiles raise readable errors.

### V3 — LLM + JD analysis + matching
- `LLM` protocol, OpenAI-compatible client (JSON mode, pydantic validation, one repair retry),
  `FakeLLM` for tests.
- `analyze_jd` → `JobAnalysis`; `match` → `Coverage` per requirement. Code adds
  deterministic keyword hits and discards hallucinated fact ids.
- **Done when:** with `FakeLLM`, invalid ids are dropped, deterministic hits are added,
  gaps are reported; the client retries once on bad JSON and raises a clear error after.

### V4 — Planning + verification
- `plan` → proposals (rewrite/add) from the LLM, normalized and id-checked.
- `verify` implements the check table above.
- **Done when:** tests prove each check catches its fabrication case (invented number,
  invented tool, borrowed fact from another job, unknown fact id) and passes honest rewrites,
  including the "direct coverage lets you use the JD's term" case.

### V5 — Build: relevance, fitting, compile
- Deterministic relevance scores; reorder bullets in each entry and skills in each line by
  relevance; fit loop drops lowest-relevance bullets (≥1 bullet per entry kept) until the
  page budget is met; compile with `latexmk`/`pdflatex`/`tectonic`.
- **Done when:** fit loop tested with a fake page counter (drops in the right order, stops at
  budget, reports what it dropped); real compile test passes when a TeX engine is installed.

### V6 — Runs, review, CLI
- `Run` persisted as JSON; `pipeline.start_run / decide / regenerate / finalize`.
- CLI: `bob tailor jd.txt` → coverage + proposals; `bob review <run>` interactive
  accept/reject/edit/regenerate; `bob finalize <run>` → PDF.
- **Done when:** an end-to-end test (FakeLLM + fake compiler) goes JD → proposals → decisions →
  final `.tex` that contains exactly the accepted changes, and the run reloads from disk.

### V7 — HTTP API
- FastAPI over `pipeline.py`: create run, get run, decide/edit/regenerate a proposal,
  finalize, download PDF/tex, read profile and resume outline.
- **Done when:** API tests with `TestClient` cover the full flow.

### Later (not in this pass)
- Frontend rework: per-proposal review cards, coverage panel (existing React app needs new API calls).
- Onboarding from notes/READMEs: LLM proposes facts from raw text, user confirms.
- Bullet bank: reuse previously accepted phrasings for similar requirements.
- Application tracker view, summary-paragraph support, browser extension for JD capture,
  MCP server so chat assistants can call Bob.
