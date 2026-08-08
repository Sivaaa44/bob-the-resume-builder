from langgraph.types import interrupt
from state import ResumeTailorState

def human_review_node(state: ResumeTailorState) -> dict:
    pdf_path = state.get("pdf_path")
    page_count = state.get("page_count", 0)
    gap_report = state.get("gap_report", "")
    tex_diff = state.get("tex_diff", "")
    condense_attempts = state.get("condense_attempts", 0)

    overflow_warning = ""
    if page_count and page_count > 1:
        overflow_warning = f"\n⚠️ WARNING: PDF is still {page_count} pages after {condense_attempts} condense passes!"

    review_payload = {
        "pdf_path": pdf_path,
        "page_count": page_count,
        "gap_report": gap_report,
        "tex_diff": tex_diff,
        "overflow_warning": overflow_warning,
        "prompt": "Options: [1] approve | [2] regenerate:<feedback text> | [3] abort"
    }

    # Interrupt graph execution and present payload for review
    human_response = interrupt(review_payload)

    if not human_response:
        return {"status": "approved"}

    response_str = str(human_response).strip()

    if response_str == "approve" or response_str == "1":
        return {"status": "approved"}
    elif response_str.startswith("regenerate:") or response_str.startswith("2:"):
        feedback = response_str.split(":", 1)[1].strip()
        return {"human_feedback": feedback, "status": "running"}
    elif response_str == "abort" or response_str == "3":
        return {"status": "aborted"}
    else:
        # Default fallback to feedback if text provided
        return {"human_feedback": response_str, "status": "running"}
