from state import ResumeTailorState
from utils.llm import get_llm

def generate_gap_report_node(state: ResumeTailorState) -> dict:
    match_result = state.get("match_result", {"matched": [], "partial": [], "missing": []})
    missing = match_result.get("missing", [])

    if not missing:
        report = "### Gap Analysis Report\n\nNo skill gaps detected! All required skills matched candidate ground truth."
        return {"gap_report": report}

    llm = get_llm()

    if llm:
        prompt = f"""You are a technical career coach. Produce a concise Gap Analysis Report ONLY for the missing skills listed below.
Do not discuss matched or partial skills.

Missing Skills:
{missing}

For each missing item:
1. Provide a 1-sentence plain description of the gap.
2. Provide 1 suggested angle to close/bridge the gap (prefer retrofitting existing projects like DeepMidWicket or past internship experiences over starting a new project from scratch).

Keep the report structured, clear, and action-oriented in markdown format.
"""
        res = llm.invoke(prompt)
        report = res.content
    else:
        # Heuristic fallback if LLM key is absent
        lines = ["### Gap Analysis Report\n"]
        for skill in missing:
            lines.append(f"**Missing Skill**: `{skill}`")
            lines.append(f"- **Description**: The job description asks for {skill}, which is not present in your ground truth experience.")
            lines.append(f"- **Suggested Angle**: Consider retrofitting an existing project (e.g. extending DeepMidWicket by integrating a {skill} component or pipeline module).\n")
        report = "\n".join(lines)

    return {"gap_report": report}
