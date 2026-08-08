from state import ResumeTailorState

def track_application_placeholder(pdf_path: str, jd_raw: str):
    """
    V2 Hook: Application tracker integration (Sheets/Excel/Database).
    No-op for V1.
    """
    pass

def finalize_node(state: ResumeTailorState) -> dict:
    pdf_path = state.get("pdf_path")
    jd_raw = state.get("jd_raw", "")
    
    # Call tracker hook placeholder
    track_application_placeholder(pdf_path, jd_raw)

    return {"status": "approved"}
