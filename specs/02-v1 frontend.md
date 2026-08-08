# Resume Tailor Agent — 02: Frontend for V1

## Goal
A minimal web UI wrapping the existing V1 graph: paste a JD, watch it run, review the result (PDF + diff + gap report), approve/regenerate/abort inline, download the final PDF. No new agent logic — this spec only covers exposing the already-working graph over HTTP and a thin UI on top.

## Scope
In scope:
- Single-page frontend: JD textarea in, one run at a time
- Backend API wrapping the LangGraph `invoke`/`resume` cycle (the graph itself is untouched)
- Inline PDF preview + download
- Inline gap report + matched/partial/missing skill display
- Inline bullet diff (old vs new)
- The three human_review actions (approve / regenerate with feedback / abort) as buttons, not CLI input

Out of scope for this pass:
- Auth, multi-user support
- Run history / past-sessions list (that's tracker territory — separate spec)
- Editing the .tex directly in the UI

## Tech stack
- Backend: FastAPI, wrapping the existing `graph.py` — reuse the compiled graph object, don't duplicate node logic
- Frontend: React + Vite (same stack as DeepMidWicket, for consistency)
- Checkpointer: keep `MemorySaver` for now — fine since it's single-process, single-user. Note as a known limitation: state is lost if the backend restarts mid-review.

## Backend API

### `POST /run`
Starts a new session.
- Body: `{ "jd_text": string }`
- Server generates a `thread_id` (uuid), calls `graph.invoke({"jd_raw": jd_text}, config={"configurable": {"thread_id": thread_id}})`
- Graph runs until it either hits the `human_review` interrupt or completes/errors
- Response:
```json
{
  "thread_id": "...",
  "status": "awaiting_review" | "error",
  "match_result": { "matched": [...], "partial": [...], "missing": [...] },
  "gap_report": "...",
  "tex_diff": "...",
  "page_count": 1,
  "pdf_url": "/pdf/{thread_id}",
  "error": null
}
```

### `POST /decision`
Resumes a paused session.
- Body: `{ "thread_id": string, "decision": "approve" | "regenerate" | "abort", "feedback": string | null }`
- Server calls `graph.invoke(Command(resume=decision_payload), config={"configurable": {"thread_id": thread_id}})`
- `approve` → graph runs to `finalize`, END. Response `status: "approved"`, final `pdf_url`.
- `regenerate` → feedback gets attached to state, graph loops back through `rewrite_resume` → `compile_tex` → `check_pages` → `human_review` again. Response is the same shape as `/run`'s response (fresh diff, fresh PDF, `status: "awaiting_review"`).
- `abort` → `status: "aborted"`, END.

### `GET /pdf/{thread_id}`
Serves the current compiled PDF for that thread (`Content-Type: application/pdf`) — used both for the inline `<iframe>`/`<embed>` preview and as the download link. Always serves whatever the latest compiled version in state is, so it stays correct across regenerate loops without the frontend needing to re-fetch a new URL each time.

## Frontend structure

```
frontend/
  src/
    App.jsx
    components/
      JDInput.jsx        # textarea + submit button, loading state
      ReviewPanel.jsx     # gap report + matched/partial/missing lists + diff view
      PdfPreview.jsx       # <iframe> or <embed> pointing at /pdf/{thread_id}, + download link
      ReviewActions.jsx    # approve / regenerate (with feedback textarea) / abort buttons
    api.js                # thin fetch wrappers for /run and /decision
```

### State flow (frontend)
```
idle
  → (submit JD) → loading
loading
  → (POST /run resolves) → awaiting_review   [shows ReviewPanel + PdfPreview + ReviewActions]
  → (error) → error state, show message + retry
awaiting_review
  → (click approve)              → POST /decision {approve} → done  [show final PdfPreview + download, no more actions]
  → (click regenerate + type fb) → POST /decision {regenerate, feedback} → loading → awaiting_review  (loop)
  → (click abort)                 → POST /decision {abort} → aborted state, show "run aborted", allow starting a new JD
```

Track `thread_id` and current response payload in top-level React state (`useState` in `App.jsx`) — no need for a state management library or persistence beyond the current session for this pass.

### PDF preview
Use `<iframe src={pdfUrl} width="100%" height="800px" />` (or `<embed>` — iframe has better cross-browser PDF viewer fallback). Add a plain `<a href={pdfUrl} download>Download resume</a>` alongside it — browsers handle the actual download from the same URL, no separate endpoint needed.

### Diff view
`tex_diff` from the backend is a unified diff string (from `tex_edit_tool.py`). Render it as preformatted text for V1 — a proper side-by-side/highlighted diff view (e.g. via a diff-rendering library) is a nice-to-have, not required for this pass. Don't build a custom diff parser; if you want syntax highlighting later, reach for an existing React diff-viewer package rather than hand-rolling one.

## Error handling
- LaTeX compile failure surfaces from the graph as `status: "error"` with the compile error message — show it plainly in the UI rather than a blank/broken PDF preview, with a way to abort and start over.
- If `/pdf/{thread_id}` is requested for a thread that errored before ever compiling, return 404 — the frontend should only render `PdfPreview` when `pdf_url` is present in the response, not assume it always exists.

## Definition of done
- Paste a JD, get a rendered PDF preview + gap report + diff in the browser without touching the CLI
- Regenerate with feedback text visibly changes the next rewrite (same guarantee as the CLI version, just via the button)
- Download link produces the actual compiled PDF, not a stale/cached one, even after a regenerate loop
- Aborting or approving cleanly ends the session and the UI returns to a state where a new JD can be submitted