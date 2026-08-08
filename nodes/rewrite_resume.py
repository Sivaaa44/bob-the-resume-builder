import os
import json
from state import ResumeTailorState
from utils.llm import get_llm
from tools.tex_edit_tool import generate_tex_diff

def rewrite_resume_node(state: ResumeTailorState) -> dict:
    gt_path = os.path.join(os.getcwd(), "data", "ground_truth.json")
    with open(gt_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    # Read base resume if tex_content is empty
    working_tex = state.get("tex_content")
    if not working_tex:
        base_tex_path = os.path.join(os.getcwd(), "data", "base_resume.tex")
        with open(base_tex_path, "r", encoding="utf-8") as f:
            working_tex = f.read()

    match_result = state.get("match_result", {"matched": [], "partial": [], "missing": []})
    matched = match_result.get("matched", [])
    partial = match_result.get("partial", [])
    human_feedback = state.get("human_feedback")

    llm = get_llm()

    if llm:
        prompt = f"""You are a LaTeX resume tailoring expert. Tailor the base LaTeX resume to target the job description.

STRICT GUARDRAILS:
1. ONLY use skills and experience verified in Ground Truth: {json.dumps(ground_truth, indent=2)}
2. Allowed skills to emphasize / reword: {matched} and partial skills: {partial}
3. STRICTLY PROHIBITED: Do NOT invent or add any new tool, skill, or experience claim not explicitly in ground truth.
4. Keep full valid LaTeX formatting intact. Return ONLY valid executable LaTeX code (no markdown backticks or extra text outside LaTeX code).
5. Allowed changes:
   - Reorder bullets and sections by relevance to JD
   - Reweight project billing
   - Swap in JD terminology ONLY where candidate has the skill
   - Rewrite summary paragraph to highlight relevant matched skills
"""
        if human_feedback:
            prompt += f"\nHUMAN FEEDBACK CONSTRAINT FOR REGENERATION:\n{human_feedback}\n"

        prompt += f"\nBase LaTeX Resume:\n{working_tex}\n"

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
        # Heuristic deterministic tailoring if LLM key is absent
        new_tex = working_tex
        if matched:
            matched_str = ", ".join(matched[:5])
            # Highlight top matched skills in summary
            new_tex = new_tex.replace(
                "Software Engineer and AI Systems builder",
                f"Software Engineer specializing in {matched_str}"
            )
        if human_feedback:
            # Append feedback note if human requested feedback loop
            new_tex = new_tex.replace("% Summary Section", f"% Human Feedback Applied: {human_feedback}\n% Summary Section")

    diff = generate_tex_diff(working_tex, new_tex)

    return {
        "tex_content": new_tex,
        "tex_diff": diff,
        "human_feedback": None  # Reset feedback once processed
    }
