import os
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.types import Command

from graph import build_graph
from utils.llm import validate_groq_key

app = FastAPI(title="Resume Tailor Agent API", version="1.0.0")

# Enable CORS for local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global compiled graph instance (using MemorySaver checkpointer)
graph = build_graph()

class RunRequest(BaseModel):
    jd_text: str

class DecisionRequest(BaseModel):
    thread_id: str
    decision: str  # "approve" | "regenerate" | "abort"
    feedback: Optional[str] = None

def build_response_payload(thread_id: str, state_snapshot) -> dict:
    values = state_snapshot.values or {}
    pdf_path = values.get("pdf_path")
    status = values.get("status", "running")
    
    # Determine UI status
    if state_snapshot.next:
        ui_status = "awaiting_review"
    elif status == "approved":
        ui_status = "approved"
    elif status == "aborted":
        ui_status = "aborted"
    else:
        ui_status = status

    pdf_url = f"/api/pdf/{thread_id}" if pdf_path and os.path.exists(pdf_path) else None

    return {
        "thread_id": thread_id,
        "status": ui_status,
        "match_result": values.get("match_result", {"matched": [], "partial": [], "missing": []}),
        "gap_report": values.get("gap_report", ""),
        "tex_diff": values.get("tex_diff", ""),
        "page_count": values.get("page_count", 0),
        "condense_attempts": values.get("condense_attempts", 0),
        "pdf_url": pdf_url,
        "error": None
    }

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Resume Tailor Agent API"}

@app.post("/api/run")
def start_run(req: RunRequest):
    if not req.jd_text or not req.jd_text.strip():
        raise HTTPException(status_code=400, detail="Job description text cannot be empty.")

    # Validate key presence early
    try:
        validate_groq_key()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "jd_raw": req.jd_text.strip(),
        "condense_attempts": 0,
        "status": "running"
    }

    try:
        # Run graph until interrupt or END
        for _ in graph.stream(initial_state, config, stream_mode="values"):
            pass

        state_snapshot = graph.get_state(config)
        return build_response_payload(thread_id, state_snapshot)

    except Exception as e:
        return {
            "thread_id": thread_id,
            "status": "error",
            "match_result": {"matched": [], "partial": [], "missing": []},
            "gap_report": "",
            "tex_diff": "",
            "page_count": 0,
            "condense_attempts": 0,
            "pdf_url": None,
            "error": str(e)
        }

@app.post("/api/decision")
def submit_decision(req: DecisionRequest):
    if not req.thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required.")

    config = {"configurable": {"thread_id": req.thread_id}}
    state_snapshot = graph.get_state(config)

    if not state_snapshot.values:
        raise HTTPException(status_code=404, detail=f"No session found for thread_id {req.thread_id}")

    # Format decision payload for human_review interrupt
    decision_clean = req.decision.lower().strip()
    if decision_clean == "approve":
        resume_payload = "approve"
    elif decision_clean == "abort":
        resume_payload = "abort"
    elif decision_clean == "regenerate":
        fb = req.feedback.strip() if req.feedback and req.feedback.strip() else "Please refine matching skills and optimize phrasing."
        resume_payload = f"regenerate:{fb}"
    else:
        resume_payload = decision_clean

    try:
        graph.invoke(Command(resume=resume_payload), config)
        updated_snapshot = graph.get_state(config)
        return build_response_payload(req.thread_id, updated_snapshot)

    except Exception as e:
        return {
            "thread_id": req.thread_id,
            "status": "error",
            "match_result": state_snapshot.values.get("match_result", {"matched": [], "partial": [], "missing": []}),
            "gap_report": state_snapshot.values.get("gap_report", ""),
            "tex_diff": state_snapshot.values.get("tex_diff", ""),
            "page_count": state_snapshot.values.get("page_count", 0),
            "condense_attempts": state_snapshot.values.get("condense_attempts", 0),
            "pdf_url": f"/api/pdf/{req.thread_id}",
            "error": str(e)
        }

@app.get("/api/pdf/{thread_id}")
def get_pdf(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = graph.get_state(config)

    if not state_snapshot.values:
        raise HTTPException(status_code=404, detail="Session thread not found.")

    pdf_path = state_snapshot.values.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF output file not generated yet or unavailable.")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=tailored_resume_{thread_id[:8]}.pdf"}
    )

# Mount frontend dist static files if dist exists
dist_dir = os.path.join(os.getcwd(), "frontend", "dist")
if os.path.exists(dist_dir):
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
