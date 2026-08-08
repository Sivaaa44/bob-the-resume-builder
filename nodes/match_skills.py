import json
import os
from state import ResumeTailorState, MatchResult

def match_skills_node(state: ResumeTailorState) -> dict:
    gt_path = os.path.join(os.getcwd(), "data", "ground_truth.json")
    with open(gt_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    # Flatten ground truth skills & tags
    gt_skills = set(ground_truth.get("skills", []))
    for exp in ground_truth.get("experiences", []):
        gt_skills.update(exp.get("tags", []))
    for proj in ground_truth.get("projects", []):
        gt_skills.update(proj.get("tags", []))

    gt_skills_lower = {s.lower(): s for s in gt_skills}

    jd_parsed = state.get("jd_parsed", {})
    jd_skills = jd_parsed.get("required_skills", []) + jd_parsed.get("nice_to_have", [])

    matched = []
    partial = []
    missing = []

    # Known adjacency mappings for partial matching guardrails
    adjacency_map = {
        "vector database": "Pinecone",
        "vector search": "Pinecone",
        "embeddings": "Cohere",
        "llm": "Groq",
        "sql": "SQLite",
        "relational database": "SQLite",
        "automation": "Automation Anywhere A360",
        "workflows": "ServiceNow",
        "orchestration": "MCP",
        "multi-agent": "MCP"
    }

    for skill in jd_skills:
        s_clean = skill.strip()
        s_lower = s_clean.lower()

        # Check direct exact match
        if s_lower in gt_skills_lower:
            matched.append(gt_skills_lower[s_lower])
        # Check substring match
        elif any(s_lower in g_lower for g_lower in gt_skills_lower):
            matched_name = [g for g_lower, g in gt_skills_lower.items() if s_lower in g_lower][0]
            matched.append(matched_name)
        elif any(g_lower in s_lower for g_lower in gt_skills_lower):
            matched_name = [g for g_lower, g in gt_skills_lower.items() if g_lower in s_lower][0]
            matched.append(matched_name)
        # Check partial/adjacent mapping
        elif any(adj in s_lower for adj in adjacency_map):
            partial.append(s_clean)
        else:
            missing.append(s_clean)

    # Deduplicate while preserving order
    matched = list(dict.fromkeys(matched))
    partial = list(dict.fromkeys(partial))
    missing = list(dict.fromkeys(missing))

    match_result: MatchResult = {
        "matched": matched,
        "partial": partial,
        "missing": missing
    }

    return {"match_result": match_result}
