import pytest

from bob.cli import main
from bob.profile.model import Fact, Profile
from bob.profile.store import ProfileError, dump_profile, load_profile, save_profile, seed_profile
from bob.terms import contains_term, find_terms
from bob.tex.parser import parse


# ---------- term matching ----------

@pytest.mark.parametrize(
    "text, term, hit",
    [
        ("Built services in Go", "Go", True),
        ("Deployed on Google Cloud", "Go", False),
        ("Wrote JavaScript", "Java", False),
        ("Wrote C# services", "C", False),
        ("Wrote C# services", "C#", True),
        ("Used vector databases", "vector database", True),
        ("Used vector-database search", "vector database", True),
        ("Node.js and React", "node.js", True),
        ("SQLite storage", "SQL", False),
    ],
)
def test_contains_term(text, term, hit):
    assert contains_term(text, term) is hit


def test_find_terms_prefers_longer_terms():
    assert find_terms("Integrated the Adobe Sign API", ["API", "Adobe Sign API"]) == ["Adobe Sign API"]
    assert sorted(find_terms("Adobe Sign API and a REST API", ["API", "Adobe Sign API"])) == ["API", "Adobe Sign API"]


# ---------- seeding ----------

def test_seed_one_fact_per_bullet_plus_project_stack(resume_src):
    doc = parse(resume_src)
    profile = seed_profile(doc)
    bullet_facts = [f for f in profile.facts if f.text in {b.text for b in doc.bullets()}]
    assert len(bullet_facts) == len(doc.bullets())
    assert all(f.source == "resume" for f in profile.facts)
    by_text = {f.text: f for f in profile.facts}
    assert by_text["Wrote SQL transformations in Snowflake over 2M+ rows of sales data"].skills == ["Snowflake", "SQL"]
    assert by_text["Wrote SQL transformations in Snowflake over 2M+ rows of sales data"].entry == "experience.data-engineering-intern"
    stack = by_text["CricketBrain was built with FastAPI, React, SQLite, Groq"]
    assert stack.skills == ["FastAPI", "React", "SQLite", "Groq"]
    assert profile.skills["Languages"] == ["Python", "SQL", "JavaScript", "C#"]
    assert len({f.id for f in profile.facts}) == len(profile.facts)


def test_save_load_round_trip(resume_src, tmp_path):
    doc = parse(resume_src)
    profile = seed_profile(doc)
    profile.facts.append(Fact(id="g1", text="AWS Certified Cloud Practitioner", skills=["AWS"]))
    path = tmp_path / "profile.yaml"
    save_profile(profile, path, doc)
    assert load_profile(path, doc) == profile
    assert "# Data Engineering Intern — Acme Analytics" in path.read_text()


def test_load_assigns_missing_ids_and_accepts_plain_strings(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text(
        "skills: {Languages: [Python]}\n"
        "entries:\n  x.y:\n  - {id: f2, text: a}\n  - text: b\n"
        "general:\n- Speaks Spanish\n"
    )
    p = load_profile(path)
    assert [(f.id, f.text, f.entry) for f in p.facts] == [
        ("f2", "a", "x.y"), ("f3", "b", "x.y"), ("f4", "Speaks Spanish", None),
    ]


def test_load_errors_are_readable(resume_src, tmp_path):
    doc = parse(resume_src)
    path = tmp_path / "p.yaml"
    path.write_text("entries:\n  experience.nope:\n  - {id: f1, text: a}\n  - {id: f1, text: b}\n")
    with pytest.raises(ProfileError) as e:
        load_profile(path, doc)
    assert "duplicate fact id f1" in str(e.value)
    assert "unknown resume entry 'experience.nope'" in str(e.value)

    path.write_text("entries: [unclosed")
    with pytest.raises(ProfileError, match="invalid YAML"):
        load_profile(path)


def test_all_skills_dedupes_case_insensitively():
    p = Profile(facts=[Fact(id="f1", text="x", skills=["python", "Pinecone"])], skills={"L": ["Python"]})
    assert p.all_skills() == ["Python", "Pinecone"]


def test_dump_without_doc():
    text = dump_profile(Profile(facts=[Fact(id="f1", text="x")]))
    assert "general:" in text and "f1" in text


# ---------- CLI ----------

def test_cli_init_and_facts(tmp_path, capsys):
    from tests.conftest import FIXTURES

    home = tmp_path / "ws"
    assert main(["init", str(FIXTURES / "resume.tex"), "--home", str(home)]) == 0
    assert (home / "resume.tex").exists() and (home / "profile.yaml").exists()
    assert main(["init", str(FIXTURES / "resume.tex"), "--home", str(home)]) == 1  # no silent overwrite
    assert main(["facts", "--home", str(home)]) == 0
    assert "Data Engineering Intern" in capsys.readouterr().out
