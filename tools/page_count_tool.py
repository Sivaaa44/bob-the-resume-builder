import os
from pypdf import PdfReader

def get_page_count(pdf_path: str) -> int:
    """
    Returns page count of a PDF file using pypdf.
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return 0
    try:
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception as e:
        print(f"Error reading PDF page count: {e}")
        return 0
