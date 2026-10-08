"""Step 1 — read the job description into a list of requirements."""

from typing import Literal

from pydantic import BaseModel, Field

from bob.llm.base import LLM
from bob.tailor.models import JobAnalysis, Requirement

MAX_REQUIREMENTS = 20

SYSTEM = """\
You extract hiring requirements from a job description for a resume-tailoring tool.

Rules:
- One requirement per distinct skill, technology, or responsibility. Split compound lines
  ("Python or Go; experience with AWS") into separate requirements.
- importance = "must" for required/minimum qualifications and core responsibilities,
  "nice" for preferred/bonus/plus items.
- keywords = the exact words or short phrases from the JD an applicant-tracking system would scan
  for (tools, languages, methods). Copy the JD's spelling. 1-4 per requirement.
- Ignore benefits, company boilerplate, EEO statements, salary, location and visa text.
- Do not invent requirements that are not in the text.
"""


class _RequirementOut(BaseModel):
    text: str
    importance: Literal["must", "nice"]
    keywords: list[str] = Field(default_factory=list)


class JDExtraction(BaseModel):
    title: str = ""
    company: str = ""
    requirements: list[_RequirementOut]


def analyze_jd(jd_text: str, llm: LLM) -> JobAnalysis:
    out = llm.complete_json(SYSTEM, f"Job description:\n\"\"\"\n{jd_text.strip()}\n\"\"\"", JDExtraction)
    reqs: list[Requirement] = []
    seen: set[str] = set()
    for r in out.requirements:
        text = r.text.strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        keywords = list(dict.fromkeys(k.strip() for k in r.keywords if k.strip()))
        reqs.append(Requirement(id=f"r{len(reqs) + 1}", text=text, importance=r.importance, keywords=keywords))
        if len(reqs) == MAX_REQUIREMENTS:
            break
    # must-haves first so every later step sees the important ones first
    reqs.sort(key=lambda r: r.importance != "must")
    for k, r in enumerate(reqs, start=1):
        r.id = f"r{k}"
    return JobAnalysis(title=out.title.strip(), company=out.company.strip(), requirements=reqs)
