import re
from state import ResumeTailorState
from utils.llm import get_llm
from tools.tex_edit_tool import generate_tex_diff

def condense_resume_node(state: ResumeTailorState) -> dict:
    tex_content = state.get("tex_content", "")
    attempts = state.get("condense_attempts", 0) + 1
    match_result = state.get("match_result", {"matched": [], "partial": [], "missing": []})
    
    llm = get_llm()

    if llm:
        prompt = f"""The compiled LaTeX resume was OVER PAGE LIMIT (Page Count > 1).
Condense pass attempt {attempts} of 3.

CRITICAL CONDENSATION RULES (specs/03-langchain_implementation.md):
1. INTERN EXPERIENCES & EDUCATION: Do NOT remove, delete, or strip ANY bullet points or entries in Education or Intern Experiences! They MUST remain intact.
2. LATEX SPACING FIRST: Tighten vertical spacing, margins, itemsep, parsep, topsep, and section vspace (e.g. reduce geometry margins top/bottom=0.7cm, itemsep=0.00cm, vspace=1pt).
3. SUMMARY & PROJECTS ONLY: If text conciseness editing is required, adjust ONLY the Summary paragraph or Technical Project bullets to be slightly more compact.
4. DO NOT make entire sections or experience bullet points disappear.

Current LaTeX Resume:
{tex_content}

Return ONLY valid executable LaTeX code (from \\documentclass to \\end{{document}}).
"""
        res = llm.invoke(prompt)
        new_tex = res.content.strip()

        if new_tex.startswith("```latex"):
            new_tex = new_tex[8:]
        if new_tex.startswith("```"):
            new_tex = new_tex[3:]
        if new_tex.endswith("```"):
            new_tex = new_tex[:-3]
        new_tex = new_tex.strip()

        # Strict extraction between \documentclass and \end{document}
        if "\\documentclass" in new_tex and "\\end{document}" in new_tex:
            start_idx = new_tex.find("\\documentclass")
            end_idx = new_tex.rfind("\\end{document}") + len("\\end{document}")
            new_tex = new_tex[start_idx:end_idx]
        else:
            print("⚠️ [WARNING] Condense pass LLM output was incomplete or missing \\end{document}. Retaining current LaTeX.")
            new_tex = tex_content


    else:
        # Deterministic space reduction fallback preserving all bullet points
        new_tex = tex_content
        # Reduce margins & list spacing
        new_tex = new_tex.replace("top=1.0cm", "top=0.7cm")
        new_tex = new_tex.replace("bottom=1.0cm", "bottom=0.7cm")
        new_tex = new_tex.replace("left=1.5cm", "left=1.2cm")
        new_tex = new_tex.replace("right=1.5cm", "right=1.2cm")
        new_tex = new_tex.replace("itemsep=0.01cm", "itemsep=0.00cm")
        new_tex = new_tex.replace("parsep=0.01cm", "parsep=0.00cm")
        new_tex = new_tex.replace("vspace{0.08cm}", "vspace{0.02cm}")
        new_tex = new_tex.replace("vspace{0.02cm}", "vspace{0.00cm}")

    diff = generate_tex_diff(tex_content, new_tex)

    return {
        "tex_content": new_tex,
        "tex_diff": diff,
        "condense_attempts": attempts
    }

