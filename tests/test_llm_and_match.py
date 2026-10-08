import json

import httpx
import pytest

from bob.config import Settings
from bob.llm.base import LLMError, parse_json_response
from bob.llm.fake import FakeLLM
from bob.llm.openai_compat import OpenAICompatLLM, get_llm
from bob.tailor.analyze import JDExtraction, analyze_jd
from bob.tailor.match import MatchOut, coverage_score, gaps, match
from bob.tailor.models import JobAnalysis


# ---------- LLM plumbing ----------

def test_parse_json_response_tolerates_fences_and_chatter():
    reply = 'Sure! ```json\n{"title": "X", "requirements": []}\n```'
    assert parse_json_response(reply, JDExtraction).title == "X"
    with pytest.raises(ValueError, match="no JSON"):
        parse_json_response("nope", JDExtraction)
    with pytest.raises(ValueError, match="schema"):
        parse_json_response('{"requirements": [{"text": "x", "importance": "maybe"}]}', JDExtraction)


def _client(replies: list, seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        r = replies.pop(0)
        if isinstance(r, httpx.Response):
            return r
        return httpx.Response(200, json={"choices": [{"message": {"content": r}}]})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_compat_success_and_request_shape():
    seen = []
    llm = OpenAICompatLLM("https://x/v1", "k", "m", client=_client(['{"requirements": []}'], seen))
    assert llm.complete_json("sys", "usr", JDExtraction).requirements == []
    body = seen[0]
    assert body["model"] == "m" and body["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in body["messages"][0]["content"]


def test_openai_compat_repairs_once():
    seen = []
    llm = OpenAICompatLLM("https://x/v1", "k", "m", client=_client(["oops", '{"requirements": []}'], seen))
    assert llm.complete_json("s", "u", JDExtraction).requirements == []
    assert "invalid" in seen[1]["messages"][-1]["content"]


def test_openai_compat_gives_up_after_retry():
    llm = OpenAICompatLLM("https://x/v1", "k", "m", client=_client(["oops", "still oops"], []))
    with pytest.raises(LLMError, match="after a retry"):
        llm.complete_json("s", "u", JDExtraction)


def test_openai_compat_http_error():
    llm = OpenAICompatLLM("https://x/v1", "k", "m", client=_client([httpx.Response(401, text="bad key")], []))
    with pytest.raises(LLMError, match="401"):
        llm.complete_json("s", "u", JDExtraction)


def test_get_llm_needs_key_unless_local():
    with pytest.raises(LLMError, match="API key"):
        get_llm(Settings(llm_api_key="", llm_base_url="https://api.groq.com/openai/v1"))
    assert get_llm(Settings(llm_api_key="", llm_base_url="http://localhost:11434/v1"))


# ---------- analyze ----------

def test_analyze_assigns_ids_must_first_and_dedupes():
    llm = FakeLLM({JDExtraction: {"title": " ML Engineer ", "company": "Initech", "requirements": [
        {"text": "Docker experience", "importance": "nice", "keywords": ["Docker", " ", "Docker"]},
        {"text": "Python", "importance": "must", "keywords": ["Python"]},
        {"text": "python", "importance": "must", "keywords": ["Python"]},
    ]}})
    a = analyze_jd("JD text", llm)
    assert a.title == "ML Engineer"
    assert [(r.id, r.text, r.importance) for r in a.requirements] == [("r1", "Python", "must"), ("r2", "Docker experience", "nice")]
    assert a.requirement("r2").keywords == ["Docker"]
    assert "JD text" in llm.calls[0][1]


# ---------- match ----------

def test_match_drops_hallucinated_ids_and_adds_literal_hits(analysis, profile, doc):
    llm = FakeLLM({MatchOut: {"coverage": [
        {"requirement_id": "r1", "strength": "none", "fact_ids": [], "note": "?"},
        {"requirement_id": "r2", "strength": "direct", "fact_ids": ["f11", "f999"], "note": "Pinecone"},
        {"requirement_id": "r3", "strength": "direct", "fact_ids": ["f404"], "note": "made up"},
        {"requirement_id": "r99", "strength": "direct", "fact_ids": ["f1"]},
    ]}})
    cov = {c.requirement_id: c for c in match(analysis, profile, llm, doc)}

    assert cov["r1"].strength == "direct" and cov["r1"].literal          # LLM missed it; keyword "Python" is in f1
    assert "f1" in cov["r1"].fact_ids
    assert cov["r2"].strength == "direct" and cov["r2"].fact_ids == ["f11"]  # f999 dropped
    assert not cov["r2"].literal                                           # judged by LLM, not literal
    assert cov["r3"].strength == "none" and cov["r3"].fact_ids == []       # only a fake id → none
    assert cov["r4"].strength == "direct" and "f2" in cov["r4"].fact_ids   # missing from LLM, literal hit
    assert set(cov) == {"r1", "r2", "r3", "r4"}                            # r99 ignored

    prompt = llm.calls[0][1]
    assert "f11 [Data Engineering Intern]" in prompt and "r2 (must) Vector databases" in prompt


def test_gaps_and_score(analysis, profile):
    llm = FakeLLM({MatchOut: {"coverage": [
        {"requirement_id": "r2", "strength": "adjacent", "fact_ids": ["f11"]},
    ]}})
    cov = match(analysis, profile, llm)
    assert [r.id for r, _ in gaps(analysis, cov)] == ["r2", "r3"]
    # must=2 weight: r1 (2) + r4 (1) covered out of 2+2+2+1
    assert coverage_score(analysis, cov) == pytest.approx(3 / 7)
    assert coverage_score(JobAnalysis(requirements=[]), []) == 0.0
