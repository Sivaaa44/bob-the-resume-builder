from typing import TypedDict, Literal, Optional

class MatchResult(TypedDict):
    matched: list[str]       # JD terms directly present in ground truth
    partial: list[str]       # adjacent/related -- safe to reframe, not claim outright
    missing: list[str]       # real gaps

class ResumeTailorState(TypedDict):
    jd_raw: str
    jd_parsed: dict                    # required_skills, nice_to_have, seniority, yoe_gate, etc.
    match_result: MatchResult
    match_score: Optional[float]       # 0.0 to 1.0 match score between JD and resume
    constraint_type: Optional[Literal["Hard", "Soft", "None"]]
    constraint_reason: Optional[str]
    human_constraint_choice: Optional[str] # choice when paused at Hard constraint ("continue" / "abort")
    tex_content: str                   # current working .tex
    tex_diff: Optional[str]            # last-rewrite diff, shown to human
    pdf_path: Optional[str]
    page_count: Optional[int]
    condense_attempts: int             # starts at 0, cap at 3
    gap_report: Optional[str]
    human_feedback: Optional[str]      # set on regenerate
    status: Literal["running", "awaiting_review", "awaiting_constraint", "approved", "aborted"]

