from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import ResumeTailorState
from nodes.parse_jd import parse_jd_node
from nodes.match_skills import match_skills_node
from nodes.gap_report import generate_gap_report_node
from nodes.rewrite_resume import rewrite_resume_node
from nodes.compile_tex_node import compile_tex_node
from nodes.check_pages import check_pages_node
from nodes.condense_resume import condense_resume_node
from nodes.human_review import human_review_node
from nodes.finalize import finalize_node

def route_check_pages(state: ResumeTailorState) -> str:
    page_count = state.get("page_count", 0)
    condense_attempts = state.get("condense_attempts", 0)

    if page_count == 1:
        return "human_review"
    elif page_count > 1 and condense_attempts < 3:
        return "condense_resume"
    else:
        # page_count > 1 and condense_attempts >= 3, or compile failed
        return "human_review"

def route_human_review(state: ResumeTailorState) -> str:
    status = state.get("status")
    if status == "approved":
        return "finalize"
    elif status == "aborted":
        return END
    else:
        # Status is running / human_feedback set for regeneration
        return "rewrite_resume"

def build_graph():
    builder = StateGraph(ResumeTailorState)

    # Add Nodes
    builder.add_node("parse_jd", parse_jd_node)
    builder.add_node("match_skills", match_skills_node)
    builder.add_node("generate_gap_report", generate_gap_report_node)
    builder.add_node("rewrite_resume", rewrite_resume_node)
    builder.add_node("compile_tex", compile_tex_node)
    builder.add_node("check_pages", check_pages_node)
    builder.add_node("condense_resume", condense_resume_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("finalize", finalize_node)

    # Add Edges
    builder.add_edge(START, "parse_jd")
    builder.add_edge("parse_jd", "match_skills")
    builder.add_edge("match_skills", "generate_gap_report")
    builder.add_edge("generate_gap_report", "rewrite_resume")
    builder.add_edge("rewrite_resume", "compile_tex")
    builder.add_edge("compile_tex", "check_pages")

    # Conditional Routing from check_pages
    builder.add_conditional_edges(
        "check_pages",
        route_check_pages,
        {
            "human_review": "human_review",
            "condense_resume": "condense_resume"
        }
    )
    builder.add_edge("condense_resume", "compile_tex")

    # Conditional Routing from human_review
    builder.add_conditional_edges(
        "human_review",
        route_human_review,
        {
            "finalize": "finalize",
            "rewrite_resume": "rewrite_resume",
            END: END
        }
    )
    builder.add_edge("finalize", END)

    memory = MemorySaver()
    app = builder.compile(checkpointer=memory)
    return app

if __name__ == "__main__":
    graph = build_graph()
    print("Graph constructed and compiled successfully!")
