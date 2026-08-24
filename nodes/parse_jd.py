from typing import Literal
from pydantic import BaseModel, Field
from state import ResumeTailorState
from utils.llm import get_llm

class ParsedJD(BaseModel):
    required_skills: list[str] = Field(description="List of required technical skills, languages, tools, frameworks mentioned in JD")
    nice_to_have: list[str] = Field(description="Nice to have or preferred skills")
    seniority: str = Field(description="Seniority level, e.g. Intern, Junior, Entry-level, Mid, Senior, Staff, Lead")
    yoe_gate: str = Field(description="Years of experience requirement statement if any (e.g. 0-2 years, 3-5 years, 5+ years)")
    domain_keywords: list[str] = Field(description="Key domain keywords e.g. multi-agent, RPA, backend, AI, embedded, mobile")
    constraint_type: Literal["Hard", "Soft", "None"] = Field(
        description="Constraint classification: 'Hard' if role requires >2 years of experience or Senior/Lead rank beyond 0-1 YOE candidate profile; 'Soft' if role is in a slightly different domain (e.g., embedded, mobile); 'None' otherwise."
    )
    constraint_reason: str = Field(description="Brief explanation of the constraint classification.")
    match_score: float = Field(
        description="Estimated overall match score between candidate profile (~0-1 YOE, AI/Backend/RPA engineer) and JD on a scale from 0.0 to 1.0"
    )

def parse_jd_node(state: ResumeTailorState) -> dict:
    jd_raw = state.get("jd_raw", "")
    llm = get_llm()
    
    if llm:
        structured_llm = llm.with_structured_output(ParsedJD)
        prompt = f"""Extract structured information from the following Job Description (JD).
Candidate Profile Context:
- Current Status: B.E. Computer Science student (graduating 2026) with ~0-1 YOE of internship experience.
- Technical Experience: AI Agents, Python, FastAPI, MCP, Snowflake Cortex, RPA (Automation Anywhere, ServiceNow), C#/.NET, SQLite, Pinecone, LangGraph.
- Relevant Domains: AI Systems, Backend Engineering, RPA/Automation, Data Pipelines.

Classify Constraints:
- Hard Constraint: Role requires >2 YOE (e.g. 3-5 years, 5+ years) or Senior/Staff/Lead rank beyond candidate's 0-1 YOE.
- Soft Constraint: Role has a domain/stack shift (e.g. Embedded Firmware, iOS/Android Native, Design Lead).
- None: Entry-level, Junior, or 0-2 YOE role aligned with AI/Backend/RPA engineering.

Provide a match_score between 0.0 and 1.0 estimating overall match fit.

Job Description:
{jd_raw}
"""
        res: ParsedJD = structured_llm.invoke(prompt)
        parsed_dict = res.model_dump()
    else:
        # Heuristic fallback if LLM key is not present
        skills_found = []
        common_tech = ["Python", ".NET", "C#", "FastAPI", "SQLite", "Snowflake Cortex", "MCP", "Automation Anywhere A360", "ServiceNow", "Adobe Sign API", "Pinecone", "Cohere", "React", "Groq", "Agentic Systems", "NLP-to-SQL", "LangChain", "LangGraph", "RPA", "Docker", "REST APIs", "Kubernetes", "AWS"]
        for tech in common_tech:
            if tech.lower() in jd_raw.lower():
                skills_found.append(tech)
        
        # Check YOE keywords for hard constraint fallback
        jd_lower = jd_raw.lower()
        constraint_type = "None"
        constraint_reason = "Entry/Junior role within candidate profile."
        
        if any(term in jd_lower for term in ["5+ years", "5-7 years", "7+ years", "senior engineer", "staff engineer", "lead engineer", "10+ years"]):
            constraint_type = "Hard"
            constraint_reason = "JD requires Senior/Staff position or >5 YOE exceeding candidate's 0-1 YOE."
        elif any(term in jd_lower for term in ["3+ years", "3-5 years", "4+ years"]):
            constraint_type = "Hard"
            constraint_reason = "JD requires 3+ YOE exceeding candidate's 0-1 YOE."
        elif any(term in jd_lower for term in ["embedded", "firmware", "ios developer", "android native", "ui/ux designer"]):
            constraint_type = "Soft"
            constraint_reason = "JD has domain/stack shift from candidate's AI/Backend background."

        parsed_dict = {
            "required_skills": skills_found if skills_found else ["Python", "REST APIs"],
            "nice_to_have": ["Docker"],
            "seniority": "Senior" if constraint_type == "Hard" else "Engineer",
            "yoe_gate": "3+ years" if constraint_type == "Hard" else "0-2 years",
            "domain_keywords": ["Software Engineering", "AI"],
            "constraint_type": constraint_type,
            "constraint_reason": constraint_reason,
            "match_score": 0.4 if constraint_type == "Hard" else (0.6 if constraint_type == "Soft" else 0.85)
        }
        
    return {
        "jd_parsed": parsed_dict,
        "constraint_type": parsed_dict.get("constraint_type", "None"),
        "constraint_reason": parsed_dict.get("constraint_reason", ""),
        "match_score": parsed_dict.get("match_score", 0.8)
    }

