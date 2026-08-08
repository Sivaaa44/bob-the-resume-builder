import os
import subprocess
import shutil
import tempfile
from typing import Tuple, Optional

def compile_tex(tex_content: str, output_name: str = "output_resume") -> Tuple[bool, Optional[str], str]:
    """
    Compiles LaTeX content to a PDF using tectonic (or fallback pdflatex).
    Returns (success, pdf_path, stdout_stderr_log).
    """
    # Create build directory in workspace/output
    build_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(build_dir, exist_ok=True)
    
    tex_path = os.path.join(build_dir, f"{output_name}.tex")
    pdf_path = os.path.join(build_dir, f"{output_name}.pdf")

    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(tex_content)

    # Locate compiler
    local_tectonic = os.path.join(os.getcwd(), "tectonic.exe")
    if os.path.exists(local_tectonic):
        cmd = [local_tectonic, tex_path, "--outdir", build_dir]
    elif shutil.which("tectonic"):
        cmd = ["tectonic", tex_path, "--outdir", build_dir]
    elif shutil.which("pdflatex"):
        cmd = ["pdflatex", "-output-directory", build_dir, tex_path]
    else:
        return False, None, "No LaTeX compiler found (tectonic or pdflatex)."

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        log = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        if res.returncode == 0 and os.path.exists(pdf_path):
            return True, pdf_path, log
        else:
            return False, None, log
    except Exception as e:
        return False, None, f"Execution exception during TeX compilation: {str(e)}"
