"""HTTP API over pipeline.py. Run with: uvicorn bob.api:app --reload"""

from collections.abc import Callable
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from bob import pipeline
from bob.build.compile import CompileError
from bob.config import Settings, Workspace
from bob.llm.base import LLM, LLMError
from bob.llm.openai_compat import get_llm
from bob.profile.store import ProfileError
from bob.runs import Run
from bob.tailor.match import coverage_score


class StartRun(BaseModel):
    jd_text: str
    strict: bool = False


class Decision(BaseModel):
    action: Literal["accept", "reject", "edit", "reset", "regenerate"]
    text: str | None = None       # for edit
    feedback: str | None = None   # for regenerate


class RunOptions(BaseModel):
    include_skill_additions: bool


def run_view(run: Run) -> dict:
    return {**run.model_dump(), "score": round(coverage_score(run.analysis, run.coverage), 3)}


def create_app(
    workspace: Workspace | None = None,
    llm_factory: Callable[[], LLM] | None = None,
    compile_fn=None,
    settings: Settings | None = None,
) -> FastAPI:
    settings = settings or Settings()
    ws = workspace or settings.workspace
    make_llm = llm_factory or (lambda: get_llm(settings))
    app = FastAPI(title="Bob the Resume Builder")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(pipeline.PipelineError)
    async def _pipeline_error(_: Request, e: pipeline.PipelineError):
        return JSONResponse(status_code=400, content={"detail": str(e)})

    @app.exception_handler(ProfileError)
    async def _profile_error(_: Request, e: ProfileError):
        return JSONResponse(status_code=400, content={"detail": str(e)})

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
        return pipeline.load_context(ws, make_llm() if need_llm else None, settings)

    @app.get("/api/health")
    def health():
        return {"ok": True, "workspace_ready": ws.resume_path.exists() and ws.profile_path.exists()}

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
        return FileResponse(path, media_type=media, filename=f"resume-{run.id}.{kind}")

    @app.get("/api/runs/{run_id}/pdf")
    def pdf(run_id: str):
        return _output(run_id, "pdf")

    @app.get("/api/runs/{run_id}/tex")
    def tex(run_id: str):
        return _output(run_id, "tex")

    return app


app = create_app()
