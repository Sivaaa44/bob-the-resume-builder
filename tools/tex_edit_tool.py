import difflib

def generate_tex_diff(old_tex: str, new_tex: str) -> str:
    """
    Generates a unified text diff between old LaTeX and new LaTeX content.
    """
    old_lines = old_tex.splitlines(keepends=True)
    new_lines = new_tex.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="base_resume.tex",
        tofile="tailored_resume.tex"
    )
    return "".join(diff)
