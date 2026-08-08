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

Instructions to condense:
1. Identify bullet points with lowest relevance to matched skills: {match_result.get('matched')}
2. Remove or shorten lowest-relevance bullet points first.
3. Tighten section spacing or margins (e.g. reduce itemsep to 1pt or vspace).
4. Do NOT change factual details or add skills.

Current LaTeX Resume:
{tex_content}

Return ONLY valid executable LaTeX code.
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
    else:
        # Deterministic space reduction fallback
        new_tex = tex_content
        # Reduce margins & list spacing
        new_tex = new_tex.replace("margin=0.5in", "margin=0.4in")
        new_tex = new_tex.replace("itemsep=2pt", "itemsep=0pt")
        new_tex = new_tex.replace("vspace{4pt}", "vspace{1pt}")
        # Trim last item in itemize blocks if still condensing
        if attempts >= 2:
            new_tex = re.sub(r"(\\item[^\n]+\n)(\\end\{itemize\})", r"\2", new_tex, count=1)

    diff = generate_tex_diff(tex_content, new_tex)

    return {
        "tex_content": new_tex,
        "tex_diff": diff,
        "condense_attempts": attempts
    }
