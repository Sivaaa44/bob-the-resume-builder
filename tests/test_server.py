import unittest
import os
from unittest.mock import patch
from fastapi.testclient import TestClient

os.environ["GROQ_API_KEY"] = "mock_groq_key_for_tests"

from server import app

client = TestClient(app)

class TestServerAPI(unittest.TestCase):

    def test_01_health_check(self):
        res = client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    @patch("nodes.parse_jd.get_llm", return_value=None)
    @patch("nodes.gap_report.get_llm", return_value=None)
    @patch("nodes.rewrite_resume.get_llm", return_value=None)
    @patch("nodes.condense_resume.get_llm", return_value=None)
    @patch("utils.llm.validate_groq_key", return_value="mock_key")
    def test_02_run_endpoint(self, mock_val, mock_llm4, mock_llm3, mock_llm2, mock_llm1):
        jd_payload = {"jd_text": "Looking for Python FastAPI software engineer with SQLite and Docker experience."}
        res = client.post("/api/run", json=jd_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        if data.get("status") == "error":
            print(f"\n[DEBUG] Server Error: {data.get('error')}\n")
        self.assertIn("thread_id", data)
        self.assertEqual(data["status"], "awaiting_review")
        self.assertIn("matched", data["match_result"])

        thread_id = data["thread_id"]

        # Test decision approve
        decision_payload = {"thread_id": thread_id, "decision": "approve"}
        res_dec = client.post("/api/decision", json=decision_payload)
        self.assertEqual(res_dec.status_code, 200)
        dec_data = res_dec.json()
        self.assertEqual(dec_data["status"], "approved")

        # Test PDF retrieval
        res_pdf = client.get(f"/api/pdf/{thread_id}")
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf.headers["content-type"], "application/pdf")

if __name__ == "__main__":
    unittest.main()
