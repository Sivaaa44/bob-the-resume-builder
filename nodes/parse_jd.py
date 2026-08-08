from pydantic import BaseModel, Field
from state import ResumeTailorState
from utils.llm import get_llm

class ParsedJD(BaseModel):
    required_skills: list[str] = Field(description="List of required technical skills, languages, tools, frameworks mentioned in JD")
    nice_to_have: list[str] = Field(description="Nice to have or preferred skills")
    seniority: str = Field(description="Seniority level, e.g. Intern, Junior, Senior, Staff")
    yoe_gate: str = Field(description="Years of experience requirement statement if any")
    domain_keywords: list[str] = Field(description="Key domain keywords e.g. multi-agent, RPA, backend")

def parse_jd_node(state: ResumeTailorState) -> dict:
    jd_raw = state.get("jd_raw", "")
    llm = get_llm()
    
    if llm:
        structured_llm = llm.with_structured_output(ParsedJD)
        prompt = f"""Extract structured information from the following Job Description (JD).
No creative writing -- strictly extract facts present in text.

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
        
        parsed_dict = {
            "required_skills": skills_found if skills_found else ["Python", "REST APIs"],
            "nice_to_have": ["Docker"],
            "seniority": "Engineer",
            "yoe_gate": "0-2 years",
            "domain_keywords": ["Software Engineering", "AI"]
        }
        
    return {"jd_parsed": parsed_dict}
