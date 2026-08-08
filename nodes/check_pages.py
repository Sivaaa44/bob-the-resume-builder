from state import ResumeTailorState
from tools.page_count_tool import get_page_count

def check_pages_node(state: ResumeTailorState) -> dict:
    pdf_path = state.get("pdf_path")
    pages = get_page_count(pdf_path) if pdf_path else 0
    return {"page_count": pages}
