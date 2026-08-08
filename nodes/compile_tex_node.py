from state import ResumeTailorState
from tools.compile_tool import compile_tex

def compile_tex_node(state: ResumeTailorState) -> dict:
    tex_content = state.get("tex_content", "")
    success, pdf_path, log = compile_tex(tex_content, output_name="tailored_resume")
    
    if success:
        return {
            "pdf_path": pdf_path
        }
    else:
        existing_report = state.get("gap_report", "") or ""
        error_msg = f"\n\n### LaTeX Compilation Error\nCompilation failed with log:\n```\n{log[:1000]}\n```"
        return {
            "pdf_path": None,
            "gap_report": existing_report + error_msg
        }
