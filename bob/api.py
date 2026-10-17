"""HTTP API over pipeline.py. Run with: uvicorn bob.api:app --reload"""

from collections.abc import Callable
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from bob import pipeline
from bob.build.compile import CompileError
from bob.config import Settings, Workspace, save_settings
from bob.llm.base import LLM, LLMError
from bob.llm.openai_compat import get_llm
from bob.profile.model import Fact, Profile
from bob.profile.store import ProfileError, assign_missing_ids, save_profile, validate_profile
from bob.runs import Run, usage_stats
from bob.setup import init_workspace, outline_stats, outline_warnings
from bob.tailor.match import coverage_score
from bob.tex.parser import ParseError, parse


class StartRun(BaseModel):
    jd_text: str
    strict: bool = False


class Decision(BaseModel):
    action: Literal["accept", "reject", "edit", "reset", "regenerate"]
    text: str | None = None       # for edit
    feedback: str | None = None   # for regenerate


class RunOptions(BaseModel):
    include_skill_additions: bool


class ResumeUpload(BaseModel):
    tex: str


class FactIn(BaseModel):
    id: str | None = None          # new facts from the editor have no id yet
    text: str
    entry: str | None = None
    skills: list[str] = []
    source: Literal["resume", "user"] = "user"


class ProfileIn(BaseModel):
    facts: list[FactIn]
    skills: dict[str, list[str]] = {}


class SettingsIn(BaseModel):
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None   # write-only: never sent back to the browser
    max_pages: int | None = None


class _Ping(BaseModel):
    ok: bool


def run_view(run: Run) -> dict:
    return {**run.model_dump(), "score": round(coverage_score(run.analysis, run.coverage), 3),
            "tokens": run.total_usage.model_dump() | {"total": run.total_usage.total}}


def create_app(
    workspace: Workspace | None = None,
    llm_factory: Callable[[], LLM] | None = None,
    compile_fn=None,
    settings: Settings | None = None,
) -> FastAPI:
    fixed_settings = settings
    ws = workspace or (settings or Settings()).workspace

    def current_settings() -> Settings:
        # re-read per request so keys/models saved from the Settings page apply without a restart
        return fixed_settings or Settings.load(ws.root)

    make_llm = llm_factory or (lambda: get_llm(current_settings()))
    app = FastAPI(title="Bob the Resume Builder")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(pipeline.PipelineError)
    async def _pipeline_error(_: Request, e: pipeline.PipelineError):
        return JSONResponse(status_code=400, content={"detail": str(e)})

    @app.exception_handler(ProfileError)
    async def _profile_error(_: Request, e: ProfileError):
        return JSONResponse(status_code=400, content={"detail": str(e)})

    @app.exception_handler(ParseError)
    async def _parse_error(_: Request, e: ParseError):
        return JSONResponse(status_code=400, content={"detail": f"Couldn't read that .tex: {e}"})

    @app.exception_handler(KeyError)
    async def _not_found(_: Request, e: KeyError):
        return JSONResponse(status_code=404, content={"detail": e.args[0] if e.args else "not found"})

    @app.exception_handler(LLMError)
    async def _llm_error(_: Request, e: LLMError):
        return JSONResponse(status_code=502, content={"detail": str(e)})

    @app.exception_handler(CompileError)
    async def _compile_error(_: Request, e: CompileError):
        return JSONResponse(status_code=422, content={"detail": str(e)})

    def ctx(need_llm: bool = False) -> pipeline.Context:
        # loaded per request so edits to profile.yaml are picked up immediately
        return pipeline.load_context(ws, make_llm() if need_llm else None, current_settings())

    @app.get("/api/health")
    def health():
        s = current_settings()
        return {"ok": True, "workspace_ready": ws.ready, "has_llm_key": s.has_llm_key, "llm_model": s.llm_model}

    # ---------- setup: import resume, edit facts, settings ----------

    @app.post("/api/setup/preview")
    def setup_preview(body: ResumeUpload):
        """Parse without saving, so the user can check how Bob read their resume."""
        doc = parse(body.tex)
        return {"outline": doc.model_dump(exclude={"source"}), "stats": outline_stats(doc),
                "warnings": outline_warnings(doc), "replacing": ws.ready}

    @app.post("/api/setup/import")
    def setup_import(body: ResumeUpload):
        result = init_workspace(ws, body.tex)
        return {"stats": outline_stats(result.doc), "facts": len(result.profile.facts),
                "kept": len(result.kept), "orphaned": [f.model_dump() for f in result.orphaned],
                "warnings": outline_warnings(result.doc)}

    @app.put("/api/profile")
    def update_profile(body: ProfileIn):
        c = ctx()
        raw = [f.model_dump() for f in body.facts if f.text.strip()]
        assign_missing_ids(raw)
        skills = {cat.strip(): [x.strip() for x in items if x.strip()]
                  for cat, items in body.skills.items() if cat.strip()}
        profile = Profile(facts=[Fact(**{**f, "text": f["text"].strip(),
                                         "skills": [x.strip() for x in f["skills"] if x.strip()]}) for f in raw],
                          skills=skills)
        validate_profile(profile, c.doc)
        save_profile(profile, ws.profile_path, c.doc)
        return profile.model_dump()

    @app.get("/api/settings")
    def get_settings():
        s = current_settings()
        key = s.llm_api_key
        return {"llm_base_url": s.llm_base_url, "llm_model": s.llm_model, "max_pages": s.max_pages,
                "has_key": bool(key), "key_hint": f"…{key[-4:]}" if len(key) >= 8 else ("set" if key else "")}

    @app.put("/api/settings")
    def put_settings(body: SettingsIn):
        if body.max_pages is not None and not 1 <= body.max_pages <= 3:
            raise HTTPException(400, "max_pages must be 1, 2 or 3")
        values = body.model_dump()
        values = {k: (v.strip() if isinstance(v, str) else v) for k, v in values.items()}
        save_settings(ws, **values)
        return get_settings()

    @app.post("/api/settings/test")
    def test_settings():
        """One tiny request, so a wrong key/model shows up here rather than mid-tailoring."""
        llm = make_llm()
        out = llm.complete_json("You are a health check.", 'Reply with {"ok": true}.', _Ping)
        return {"ok": out.ok, "model": current_settings().llm_model}

    @app.get("/api/stats")
    def stats():
        return usage_stats(ctx().store.list()) if ws.ready else usage_stats([])

    @app.get("/api/resume")
    def resume():
        return ctx().doc.model_dump(exclude={"source"})

    @app.get("/api/profile")
    def profile():
        return ctx().profile.model_dump()

    @app.get("/api/runs")
    def list_runs():
        return [
            {"id": r.id, "created_at": r.created_at, "status": r.status, "title": r.analysis.title,
             "company": r.analysis.company, "score": round(coverage_score(r.analysis, r.coverage), 3)}
            for r in ctx().store.list()
        ]

    @app.post("/api/runs", status_code=201)
    def start_run(body: StartRun):
        return run_view(pipeline.start_run(ctx(need_llm=True), body.jd_text, strict=body.strict))

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        return run_view(ctx().store.load(run_id))

    @app.patch("/api/runs/{run_id}")
    def update_run(run_id: str, body: RunOptions):
        c = ctx()
        run = c.store.load(run_id)
        run.include_skill_additions = body.include_skill_additions
        c.store.save(run)
        return run_view(run)

    @app.post("/api/runs/{run_id}/proposals/{proposal_id}")
    def decide(run_id: str, proposal_id: str, body: Decision):
        c = ctx(need_llm=body.action == "regenerate")
        run = c.store.load(run_id)
        if body.action == "regenerate":
            if not body.feedback:
                raise HTTPException(400, "regenerate needs feedback")
            pipeline.regenerate(c, run, proposal_id, body.feedback)
        else:
            pipeline.decide(c, run, proposal_id, body.action, body.text)
        return run_view(run)

    @app.post("/api/runs/{run_id}/accept-all")
    def accept_all(run_id: str):
        c = ctx()
        run = c.store.load(run_id)
        pipeline.accept_all_passing(c, run)
        return run_view(run)

    @app.post("/api/runs/{run_id}/finalize")
    def finalize(run_id: str):
        c = ctx()
        return run_view(pipeline.finalize(c, c.store.load(run_id), compile_fn=compile_fn))

    @app.post("/api/runs/{run_id}/abort")
    def abort(run_id: str):
        c = ctx()
        return run_view(pipeline.abort(c, c.store.load(run_id)))

    def _output(run_id: str, kind: str):
        run = ctx().store.load(run_id)
        if not run.result:
            raise HTTPException(404, "run not finalized yet")
        path = run.result.pdf_path if kind == "pdf" else run.result.tex_path
        media = "application/pdf" if kind == "pdf" else "application/x-tex"
        # inline so the PDF previews in an <iframe>; the UI's download links use the `download` attribute
        return FileResponse(path, media_type=media, filename=f"resume-{run.id}.{kind}",
                            content_disposition_type="inline" if kind == "pdf" else "attachment")

    @app.get("/api/runs/{run_id}/pdf")
    def pdf(run_id: str):
        return _output(run_id, "pdf")

    @app.get("/api/runs/{run_id}/tex")
    def tex(run_id: str):
        return _output(run_id, "tex")

    return app


app = create_app()
