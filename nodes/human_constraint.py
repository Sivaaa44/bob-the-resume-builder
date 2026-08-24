from langgraph.types import interrupt
from state import ResumeTailorState

def human_constraint_node(state: ResumeTailorState) -> dict:
    constraint_type = state.get("constraint_type", "None")
    constraint_reason = state.get("constraint_reason", "")
    match_score = state.get("match_score", 0.0)

    constraint_payload = {
        "constraint_type": constraint_type,
        "constraint_reason": constraint_reason,
        "match_score": match_score,
        "prompt": "⚠️ HARD CONSTRAINT DETECTED! Options: [1] continue | [3] abort"
    }

    # Interrupt graph execution and wait for human confirmation
    human_response = interrupt(constraint_payload)

    if not human_response:
        return {"human_constraint_choice": "continue", "status": "running"}

    response_str = str(human_response).strip().lower()

    if response_str in ["1", "continue", "approve", "yes", "proceed"]:
        return {"human_constraint_choice": "continue", "status": "running"}
    else:
        return {"human_constraint_choice": "abort", "status": "aborted"}
