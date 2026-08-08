# Resume Tailor Agent — V1 Spec

## Goal
Given a job description (JD), produce a tailored, 1-page, compiled PDF resume from a base `.tex` file — without inventing skills the candidate doesn't have. Human approves or requests changes before the run ends.

## V1 Scope (explicitly small)
In scope:
- Single JD → single tailored resume, one run at a time
- Deterministic skill matching against a hand-authored ground-truth file (not auto-extracted from the resume yet)
- Constrained rewriting (reorder / reweight / reword — no new content)
- Page-count enforcement loop with a bounded retry count
- One human-in-the-loop checkpoint at the end (approve / regenerate with feedback / abort)

Out of scope for V1 (future versions):
- Excel/Sheets application tracker
- Auto-generating the ground-truth file from the `.tex` source
- A second early checkpoint after gap analysis (bail before rewriting)
- Multi-JD batch runs, resume version history/diffing across companies

## Tech stack
- LangGraph (Python), with a checkpointer (start with `MemorySaver`, swap to `SqliteSaver` if runs need to survive process restarts)
- LaTeX compile: `tectonic` (no system TeX install needed) — fallback to `pdflatex` if unavailable
- Page count: `pypdf`
- LLM: whatever you're already using for DeepMidWicket (keep it consistent — Groq/llama-3.3-70b or similar) for parsing/rewriting steps; these are structured-output calls, not open-ended generation

## Ground truth file (`ground_truth.json`)
Hand-authored for V1. Structure:
```json
{
  "skills": ["Python", ".NET", "Snowflake Cortex", "MCP", "Automation Anywhere A360", "ServiceNow", "Adobe Sign API", "Pinecone", "Cohere", "..."],
  "experiences": [
    {
      "id": "amd_intern",
      "title": "AI/Data Engineering Intern, AMD",
      "bullets": ["...", "..."],
      "tags": ["multi-agent systems", "Snowflake Cortex", "MCP", "Python", ".NET"]
    },
    {
      "id": "gen_intern",
      "title": "RPA Automation Intern, GEN Digital",
      "bullets": ["...", "..."],
      "tags": ["RPA", "Automation Anywhere", "ServiceNow", "Adobe Sign API"]
    }
  ],
  "projects": [
    {
      "id": "deep_mid_wicket",
      "title": "DeepMidWicket — Cricket Analytics AI Agent",
      "bullets": ["...", "..."],
      "tags": ["FastAPI", "SQLite", "React", "Groq", "agentic systems", "NLP-to-SQL"]
    }
  ]
}
```
This is the *only* source of truth for "what San actually has." The rewriter is never allowed to pull skill claims from anywhere else.

## State schema
```python
from typing import TypedDict, Literal, Optional

class MatchResult(TypedDict):
    matched: list[str]       # JD terms directly present in ground truth
    partial: list[str]       # adjacent/related — safe to reframe, not claim outright
    missing: list[str]       # real gaps

class ResumeTailorState(TypedDict):
    jd_raw: str
    jd_parsed: dict                    # required_skills, nice_to_have, seniority, yoe_gate
    match_result: MatchResult
    tex_content: str                   # current working .tex
    tex_diff: Optional[str]            # last-rewrite diff, shown to human
    pdf_path: Optional[str]
    page_count: Optional[int]
    condense_attempts: int             # starts at 0, cap at 3
    gap_report: Optional[str]
    human_feedback: Optional[str]      # set on regenerate
    status: Literal["running", "awaiting_review", "approved", "aborted"]
```

## Nodes

1. **parse_jd** — LLM call with structured output (pydantic schema). Extracts `required_skills`, `nice_to_have`, `yoe_gate` text, domain keywords. No creative writing here — force structured extraction.

2. **match_skills** — deterministic, no LLM. Set comparison between `jd_parsed` and `ground_truth.json`. Populates `match_result`. This is the guardrail node — keep it boring and rule-based.

3. **generate_gap_report** — LLM call, but constrained to the `missing` bucket only. For each missing item: (a) plain description of the gap, (b) one suggested angle to close it — prefer "retrofit an existing project" over "build something new" when there's a plausible fit (e.g. adding a RAG layer to DeepMidWicket's existing SQLite data). Runs in parallel with rewrite conceptually, but for V1 just sequence it before rewrite so it's ready for the final review screen.

4. **rewrite_resume** (tool call) — LLM-assisted, but the *only* inputs it's allowed to use for new phrasing are `match_result.matched` and `match_result.partial`. Allowed operations: reorder bullets/sections by relevance, reweight which project gets top billing, swap in JD terminology only where the underlying skill exists (e.g. "vector databases (Pinecone)"), rewrite the summary paragraph. Not allowed: adding any tag/skill not in ground truth. If `human_feedback` is set (regenerate loop), pass it in as additional constraints.

5. **compile_tex** (tool call) — shell out to `tectonic <file>.tex`, capture stdout/stderr. On compile failure, don't silently proceed — surface the LaTeX error back into `gap_report`-adjacent state and route to human_review with an error flag rather than a blank PDF.

6. **check_pages** — `pypdf`, `len(reader.pages)`. No LLM.

7. **condense_resume** (tool call) — only entered if `page_count > 1` and `condense_attempts < 3`. Takes `match_result` relevance ordering to decide what's safe to cut first (lowest-relevance bullets go first), tightens summary, trims spacing as last resort. Increments `condense_attempts`. Loops back to `compile_tex`.

8. **human_review** — `interrupt()`. Presents: compiled PDF, bullet-level diff (old vs new), gap report. Waits for one of:
   - `approve` → `finalize`, `status = "approved"`, END
   - `regenerate:<feedback text>` → sets `human_feedback`, routes back to `rewrite_resume`
   - `abort` → `status = "aborted"`, END

9. **finalize** — writes final PDF path out. (Tracker hook goes here in V2 — leave a no-op placeholder function call so it's a one-line change later.)

## Edges
```
START -> parse_jd -> match_skills -> generate_gap_report -> rewrite_resume -> compile_tex -> check_pages

check_pages (conditional):
  page_count == 1                          -> human_review
  page_count > 1 and condense_attempts < 3 -> condense_resume -> compile_tex   (loop)
  page_count > 1 and condense_attempts >= 3 -> human_review   (flag: "still overflowing after 3 condense passes")

human_review (conditional, on resume after interrupt):
  approve                -> finalize -> END
  regenerate:<feedback>  -> rewrite_resume   (loop; human_feedback carried in state)
  abort                  -> END
```

## File structure suggestion
```
resume-tailor-agent/
  graph.py              # LangGraph StateGraph definition, edges
  nodes/
    parse_jd.py
    match_skills.py
    gap_report.py
    rewrite_resume.py
    compile_tex.py
    check_pages.py
    condense_resume.py
    finalize.py
  tools/
    tex_edit_tool.py
    compile_tool.py
    page_count_tool.py
  data/
    ground_truth.json
    base_resume.tex
  state.py              # TypedDict schema
  main.py                # CLI entrypoint: takes JD text/file, runs graph, handles interrupt loop
```

## Definition of done for V1
- Can paste a JD in, get back a compiled 1-page PDF + gap report + diff, on the first LLM pass for at least a "normal fit" JD (i.e. one where you have most of the required skills)
- Page overflow triggers the condense loop and resolves within 3 attempts on a test case that's intentionally too long
- `regenerate` with feedback text actually changes the next rewrite pass (not just re-running the same prompt)
- No skill/tool appears in the output `.tex` that isn't in `ground_truth.json`