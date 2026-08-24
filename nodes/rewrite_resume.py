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

STRICT RESUME PRESERVATION GUARDRAILS (specs/03-langchain_implementation.md):

1. PRESERVE BASE RESUME STRUCTURE: The base resume must remain PREDOMINANTLY UNCHANGED. Do NOT remove, merge, reorder, or shorten bullet points. Every bullet that exists in the base resume must exist in the output, in the same position, at roughly the same length.

2. PROJECT & SUMMARY EDITS ARE WORD-LEVEL SUBSTITUTIONS, NOT REWRITES. You are swapping specific tool/keyword tokens to match JD terminology — you are NOT rewriting sentences, changing sentence structure, or changing what the bullet claims. Budget: no more than 3-5 words changed per bullet, unless the bullet contains zero JD-relevant terms, in which case change ZERO words and leave it untouched.

   Example — JD emphasizes "vector search" and "RAG pipelines":
   BEFORE: "Built a three-tool agentic system using Groq API (llama-3.3-70b) with NLP-to-SQL pipeline for cricket analytics queries"
   AFTER:  "Built a three-tool agentic RAG system using Groq API (llama-3.3-70b) with NLP-to-SQL pipeline for cricket analytics queries"
   (Only "agentic" -> "agentic RAG" changed. Everything else, including structure and length, is identical.)

   Example — JD emphasizes "distributed caching" and "low-latency systems":
   BEFORE: "Implemented a three-layer session context system: hot memory sliding window, rolling summarization, adaptive entity ledger"
   AFTER:  "Implemented a low-latency three-layer session context system: hot memory sliding window, rolling summarization, adaptive entity ledger"
   (One word inserted. Nothing removed, nothing restructured.)

   Example — bullet has NO relevant overlap with JD (e.g. JD is backend infra, bullet is about frontend UI):
   BEFORE: "Built a ChatGPT-style sidebar UI in React with session persistence via localStorage"
   AFTER:  "Built a ChatGPT-style sidebar UI in React with session persistence via localStorage"
   (Zero words changed. Irrelevant bullets are copied VERBATIM, not paraphrased "for flow.")

   WRONG (do not do this):
   BEFORE: "Built a three-tool agentic system using Groq API (llama-3.3-70b) with NLP-to-SQL pipeline for cricket analytics queries"
   WRONG:  "Architected a multi-agent RAG pipeline leveraging LLM orchestration to deliver low-latency semantic search over structured cricket datasets"
   (This is a full rewrite with new claims, new structure, and lost information. Never do this.)

3. INTERN EXPERIENCES: Do NOT delete or shorten intern experience bullet points! Even if a point is not directly relevant to the JD, copy it VERBATIM. You may ONLY reframe/reword existing terminology to match JD phrasing where the candidate genuinely has that skill (same word-budget rule as above: 3-5 words max per bullet).

4. EDUCATION & CERTIFICATIONS: Strictly UNTOUCHED. Copy verbatim, character for character.

5. GROUND TRUTH VERIFICATION: ONLY use verified facts from Ground Truth: {json.dumps(ground_truth, indent=2)}. Do NOT invent, add, or imply unverified skills, tools, or scale.

6. SELF-CHECK BEFORE RETURNING: For every bullet you changed, confirm the edit is ≤5 words different from the original and does not alter the factual claim. If a change would require more than that, do NOT make it — leave the bullet as-is instead. It is always better to under-tailor a bullet than to rewrite it.

7. Return ONLY valid executable LaTeX code (from \\documentclass to \\end{{document}}). No markdown commentary.
"""
        if human_feedback:
            prompt += f"\nHUMAN FEEDBACK CONSTRAINT FOR REGENERATION:\n{human_feedback}\n"

        prompt += f"\nBase LaTeX Resume:\n{working_tex}\n"

        res = llm.invoke(prompt)
        new_tex = res.content.strip()
        
        # Clean code block backticks
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
            # If LLM response was truncated or failed to produce complete LaTeX document, fallback safely
            print("⚠️ [WARNING] LLM output was incomplete or missing \\end{document}. Retaining working base LaTeX.")
            new_tex = working_tex


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
