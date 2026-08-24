import unittest
import os
import json
from unittest.mock import patch, MagicMock

from state import ResumeTailorState
from nodes.parse_jd import parse_jd_node
from nodes.match_skills import match_skills_node
from nodes.gap_report import generate_gap_report_node
from nodes.rewrite_resume import rewrite_resume_node
from nodes.compile_tex_node import compile_tex_node
from nodes.check_pages import check_pages_node
from nodes.condense_resume import condense_resume_node
from graph import build_graph
from langgraph.types import Command

class TestResumeTailorAgent(unittest.TestCase):

    def setUp(self):
        self.sample_jd = """
        We are seeking a Software Engineer to join our AI team.
        Required Skills: Python, FastAPI, SQLite, MCP, Snowflake Cortex, Kubernetes, Docker.
        Nice to have: Pinecone, React.
        Requirements: 0-2 years experience.
        """
        self.hard_jd = """
        We are looking for a Senior Staff AI Architect.
        Requirements: 7+ years of experience leading multi-agent enterprise infrastructure.
        Seniority: Staff / Principal.
        """

    @patch("nodes.parse_jd.get_llm", return_value=None)
    def test_01_parse_jd(self, mock_llm):
        state: ResumeTailorState = {"jd_raw": self.sample_jd, "condense_attempts": 0, "status": "running"}
        res = parse_jd_node(state)
        self.assertIn("jd_parsed", res)
        parsed = res["jd_parsed"]
        self.assertIn("required_skills", parsed)
        self.assertEqual(res["constraint_type"], "None")
        self.assertGreaterEqual(res["match_score"], 0.0)

    @patch("nodes.parse_jd.get_llm", return_value=None)
    def test_01b_parse_jd_hard_constraint(self, mock_llm):
        state: ResumeTailorState = {"jd_raw": self.hard_jd, "condense_attempts": 0, "status": "running"}
        res = parse_jd_node(state)
        self.assertEqual(res["constraint_type"], "Hard")
        self.assertIn("Senior/Staff", res["constraint_reason"])
        self.assertLessEqual(res["match_score"], 0.5)

    def test_02_match_skills(self):
        parsed_jd = {
            "required_skills": ["Python", "FastAPI", "SQLite", "MCP", "Snowflake Cortex", "Kubernetes"],
            "nice_to_have": ["Pinecone", "React"]
        }
        state: ResumeTailorState = {"jd_raw": self.sample_jd, "jd_parsed": parsed_jd, "condense_attempts": 0, "status": "running"}
        res = match_skills_node(state)
        match_res = res["match_result"]
        
        # Verify deterministic classification
        self.assertIn("Python", match_res["matched"])
        self.assertIn("FastAPI", match_res["matched"])
        self.assertIn("Snowflake Cortex", match_res["matched"])
        self.assertIn("Kubernetes", match_res["missing"])
        self.assertIn("match_score", res)
        self.assertGreater(res["match_score"], 0.5)

    @patch("nodes.gap_report.get_llm", return_value=None)
    def test_03_generate_gap_report(self, mock_llm):
        match_result = {
            "matched": ["Python", "FastAPI"],
            "partial": [],
            "missing": ["Kubernetes", "AWS"]
        }
        state: ResumeTailorState = {"jd_raw": self.sample_jd, "match_result": match_result, "match_score": 0.75, "constraint_type": "None", "condense_attempts": 0, "status": "running"}
        res = generate_gap_report_node(state)
        report = res["gap_report"]
        self.assertIn("Kubernetes", report)
        self.assertIn("75%", report)

    @patch("nodes.rewrite_resume.get_llm", return_value=None)
    def test_04_rewrite_resume(self, mock_llm):
        match_result = {
            "matched": ["Python", "FastAPI", "SQLite", "MCP", "Snowflake Cortex"],
            "partial": [],
            "missing": ["Kubernetes"]
        }
        base_tex_path = os.path.join(os.getcwd(), "data", "base_resume.tex")
        with open(base_tex_path, "r", encoding="utf-8") as f:
            base_tex = f.read()

        state: ResumeTailorState = {
            "jd_raw": self.sample_jd,
            "match_result": match_result,
            "tex_content": base_tex,
            "condense_attempts": 0,
            "status": "running"
        }
        res = rewrite_resume_node(state)
        self.assertIn("tex_content", res)
        self.assertIn("tex_diff", res)
        # Verify anti-hallucination constraint: Kubernetes must NOT be added to skills
        self.assertNotIn("Kubernetes", res["tex_content"])

    def test_05_compile_and_page_count(self):
        base_tex_path = os.path.join(os.getcwd(), "data", "base_resume.tex")
        with open(base_tex_path, "r", encoding="utf-8") as f:
            base_tex = f.read()

        state: ResumeTailorState = {"tex_content": base_tex, "condense_attempts": 0, "status": "running"}
        comp_res = compile_tex_node(state)
        self.assertIsNotNone(comp_res.get("pdf_path"))

        state["pdf_path"] = comp_res["pdf_path"]
        page_res = check_pages_node(state)
        self.assertGreater(page_res["page_count"], 0)

    @patch("nodes.condense_resume.get_llm", return_value=None)
    def test_06_condense_resume_loop_preserves_intern_bullets(self, mock_llm):
        base_tex_path = os.path.join(os.getcwd(), "data", "base_resume.tex")
        with open(base_tex_path, "r", encoding="utf-8") as f:
            base_tex = f.read()

        state: ResumeTailorState = {
            "tex_content": base_tex,
            "condense_attempts": 0,
            "match_result": {"matched": ["Python"], "partial": [], "missing": []},
            "status": "running"
        }
        res = condense_resume_node(state)
        self.assertEqual(res["condense_attempts"], 1)
        # Ensure intern experience bullet points were NOT deleted in fallback spacing adjustment
        self.assertIn("contingent worker onboarding", res["tex_content"])
        self.assertIn("multi-agent AI system", res["tex_content"])

    @patch("nodes.parse_jd.get_llm", return_value=None)
    @patch("nodes.gap_report.get_llm", return_value=None)
    @patch("nodes.rewrite_resume.get_llm", return_value=None)
    @patch("nodes.condense_resume.get_llm", return_value=None)
    def test_07_end_to_end_graph(self, mock_llm1, mock_llm2, mock_llm3, mock_llm4):
        app = build_graph()
        config = {"configurable": {"thread_id": "test_thread_1"}}
        initial_state = {
            "jd_raw": self.sample_jd,
            "condense_attempts": 0,
            "status": "running"
        }

        # Run stream until interrupt
        for event in app.stream(initial_state, config, stream_mode="values"):
            pass

        state_snap = app.get_state(config)
        self.assertTrue(state_snap.next)  # Stopped at human_review interrupt

        # Approve and resume
        app.invoke(Command(resume="approve"), config)

        final_snap = app.get_state(config)
        self.assertEqual(final_snap.values.get("status"), "approved")

    @patch("nodes.parse_jd.get_llm", return_value=None)
    @patch("nodes.gap_report.get_llm", return_value=None)
    @patch("nodes.rewrite_resume.get_llm", return_value=None)
    @patch("nodes.condense_resume.get_llm", return_value=None)
    def test_08_hard_constraint_pause_and_continue(self, mock_llm1, mock_llm2, mock_llm3, mock_llm4):
        app = build_graph()
        config = {"configurable": {"thread_id": "test_thread_hard"}}
        initial_state = {
            "jd_raw": self.hard_jd,
            "condense_attempts": 0,
            "status": "running"
        }

        # Stream until first interrupt (hard constraint pause)
        for event in app.stream(initial_state, config, stream_mode="values"):
            pass

        state_snap = app.get_state(config)
        self.assertTrue(state_snap.next)
        self.assertIn("human_constraint", state_snap.next[0])

        # Resume with "continue"
        app.invoke(Command(resume="continue"), config)

        # Continues to human_review interrupt
        state_snap_2 = app.get_state(config)
        self.assertTrue(state_snap_2.next)
        self.assertIn("human_review", state_snap_2.next[0])

        # Approve final review
        app.invoke(Command(resume="approve"), config)
        final_snap = app.get_state(config)
        self.assertEqual(final_snap.values.get("status"), "approved")


if __name__ == "__main__":
    unittest.main()

