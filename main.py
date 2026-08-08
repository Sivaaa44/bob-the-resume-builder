import os
import sys
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Force utf-8 output encoding if supported by stream
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from graph import build_graph
from utils.llm import validate_groq_key
from langgraph.types import Command

def print_separator():
    print("\n" + "=" * 70 + "\n")

def run_tailor_session(jd_text: str):
    # Enforce startup check for GROQ_API_KEY
    validate_groq_key()

    app = build_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "jd_raw": jd_text,
        "condense_attempts": 0,
        "status": "running"
    }

    print_separator()
    print("[START] Starting Resume Tailor Agent V1 execution...")
    print_separator()

    # Stream graph execution until interrupt or completion
    for event in app.stream(initial_state, config, stream_mode="values"):
        status = event.get("status")

    # Check state after initial stream pass
    state_snapshot = app.get_state(config)

    while state_snapshot.next:
        # We are paused at human_review interrupt
        values = state_snapshot.values
        pdf_path = values.get("pdf_path")
        page_count = values.get("page_count", 0)
        gap_report = values.get("gap_report", "")
        tex_diff = values.get("tex_diff", "")
        condense_attempts = values.get("condense_attempts", 0)

        print_separator()
        print("[HUMAN REVIEW CHECKPOINT]")
        print_separator()
        print(f"Compiled PDF Path : {pdf_path}")
        print(f"Page Count       : {page_count} page(s)")
        print(f"Condense Passes  : {condense_attempts}")

        if page_count and page_count > 1:
            print(f"\n[WARNING] PDF exceeds 1 page! ({page_count} pages)")

        print("\n--- GAP ANALYSIS REPORT ---")
        print(gap_report if gap_report else "No gaps recorded.")

        print("\n--- LATEX DIFF PREVIEW ---")
        if tex_diff:
            diff_lines = tex_diff.splitlines()
            # Show top 30 diff lines
            preview = "\n".join(diff_lines[:30])
            print(preview)
            if len(diff_lines) > 30:
                print(f"... ({len(diff_lines) - 30} more lines of diff)")
        else:
            print("No diff recorded.")

        print_separator()
        print("Please choose an action:")
        print("  [1] Approve & Finalize (type '1' or 'approve')")
        print("  [2] Regenerate with feedback (type '2: <your feedback>' or 'regenerate:<feedback>')")
        print("  [3] Abort run (type '3' or 'abort')")
        print_separator()

        user_input = input("Enter choice > ").strip()
        
        if user_input == "1":
            user_action = "approve"
        elif user_input == "3":
            user_action = "abort"
        elif user_input.startswith("2:") or user_input.startswith("2"):
            if ":" in user_input:
                user_action = f"regenerate:{user_input.split(':', 1)[1].strip()}"
            else:
                fb = input("Enter feedback for regeneration > ").strip()
                user_action = f"regenerate:{fb}"
        else:
            user_action = user_input

        print(f"\nSubmitting action: '{user_action}'...")
        
        # Resume graph from interrupt
        app.invoke(Command(resume=user_action), config)
        state_snapshot = app.get_state(config)

    # Execution complete
    final_values = app.get_state(config).values
    final_status = final_values.get("status")

    print_separator()
    if final_status == "approved":
        print(f"[SUCCESS] Resume tailored & approved.")
        print(f"Final PDF output location: {final_values.get('pdf_path')}")
    else:
        print("[ABORTED] Session aborted by user or graph exit.")
    print_separator()

if __name__ == "__main__":
    # Check GROQ_API_KEY early on CLI launch
    try:
        validate_groq_key()
    except ValueError as e:
        print(f"\n❌ STARTUP ERROR:\n{e}\n")
        sys.exit(1)

    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            jd_input = f.read()
    else:
        print("Paste Job Description (JD) text below (press Ctrl+Z or Ctrl+D on empty line when done):")
        jd_lines = sys.stdin.read()
        jd_input = jd_lines if jd_lines.strip() else """
Looking for an AI/Data Engineer with strong skills in Python, FastAPI, SQLite, multi-agent systems, Snowflake Cortex, MCP, vector databases (Pinecone), and LangGraph.
Requirements:
- 0-2 years experience building AI agents and data pipelines
- Strong background in Python, C#, and REST APIs
- Experience with Kubernetes, Docker, and AWS is a plus
"""

    run_tailor_session(jd_input)
