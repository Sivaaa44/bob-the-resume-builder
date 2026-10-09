import pytest

from bob import pipeline
from bob.build.compile import CompileResult
from bob.cli import format_run, main, review_loop
from bob.tex.parser import parse
from tests.conftest import ACME, FIXTURES, GLOBEX, pdflatex_pages, scripted_llm


@pytest.fixture
def ctx(workspace):
    return pipeline.load_context(workspace, scripted_llm())


def fake_compile(pages: int):
    def compile_fn(tex, workdir, name="resume", search_dirs=()):
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / f"{name}.tex").write_text(tex)
        (workdir / f"{name}.pdf").write_bytes(b"%PDF-fake")
        return CompileResult(pdf_path=workdir / f"{name}.pdf", pages=pages, log="")
    return compile_fn


def test_start_run_verifies_and_persists(ctx):
    run = pipeline.start_run(ctx, (FIXTURES / "jd.txt").read_text())
    assert [p.status for p in run.proposals] == ["pending", "pending", "blocked", "pending"]
    assert "Kubernetes" in run.proposals[2].errors[0].message
    assert run.skills_added == ["Kubernetes"]
    assert ctx.store.load(run.id) == run
    assert "initech-machine-learning-engineer" in run.id


def test_token_usage_is_recorded_per_step(ctx):
    from bob.tailor.plan import PlanOut

    run = pipeline.start_run(ctx, "JD")
    assert set(run.token_usage) == {"analyze", "match", "plan"}  # verify uses no LLM unless strict
    assert all(u.calls == 1 and u.total > 0 for u in run.token_usage.values())
    ctx.llm.responses[PlanOut] = {"proposals": [{"kind": "rewrite", "bullet_id": f"{ACME}.b3", "fact_ids": ["f3"],
                                                 "new_text": "Gave LLM agents internal tools via an MCP server"}]}
    pipeline.regenerate(ctx, run, "p3", "shorter")
    saved = ctx.store.load(run.id)
    assert saved.token_usage["regenerate"].calls == 1
    assert saved.total_usage.total == sum(u.total for u in saved.token_usage.values())


def test_full_flow_builds_exactly_the_accepted_changes(ctx, tmp_path, resume_src):
    pdflatex_pages(resume_src, tmp_path)  # skip without TeX
    run = pipeline.start_run(ctx, "JD")
    pipeline.decide(ctx, run, "p1", "accept")
    pipeline.decide(ctx, run, "p2", "accept")
    with pytest.raises(pipeline.PipelineError, match="failed verification"):
        pipeline.decide(ctx, run, "p3", "accept")
    edited = pipeline.decide(ctx, run, "p3", "edit", "Exposed internal tools to LLM agents via an MCP server")
    assert edited.status == "edited" and edited.errors == []
    pipeline.decide(ctx, run, "p4", "reject")
    run.include_skill_additions = False  # the user doesn't want Kubernetes listed

    run = pipeline.finalize(ctx, run)
    assert run.status == "finalized" and run.result.pages == 1 and run.result.fits
    tex = open(run.result.tex_path).read()
    out = parse(tex)
    assert [b.text for b in out.entry(ACME).bullets] == [
        "Cut report generation time by 40% with a multi-agent Python pipeline",           # p1, r1 must
        "Indexed 50k support tickets in a vector database (Pinecone) for semantic search",  # p2 added
        "Wrote SQL transformations in Snowflake over 2M+ rows of sales data",              # r4 nice
        "Exposed internal tools to LLM agents via an MCP server",                          # p3 as edited
    ]
    assert r"\textbf{Python}" in tex
    assert [b.text for b in out.entry(GLOBEX).bullets] == [b.text for b in ctx.doc.entry(GLOBEX).bullets]  # p4 rejected
    assert out.skill_line("technical-skills.tools").items[0] == "Snowflake"
    assert "Kubernetes" not in tex
    assert ctx.store.load(run.id).result == run.result


def test_regenerate_replaces_one_proposal(ctx):
    from bob.tailor.plan import PlanOut

    run = pipeline.start_run(ctx, "JD")
    ctx.llm.responses[PlanOut] = {"proposals": [{"kind": "rewrite", "bullet_id": f"{ACME}.b3", "fact_ids": ["f3"],
                                                 "new_text": "Gave LLM agents access to internal tools via an MCP server"}]}
    new = pipeline.regenerate(ctx, run, "p3", "drop the Kubernetes part")
    assert (new.id, new.status) == ("p3", "pending")
    assert ctx.store.load(run.id).proposal("p3").new_text.startswith("Gave LLM agents")


def test_over_budget_drops_and_reports(ctx):
    run = pipeline.start_run(ctx, "JD")
    pipeline.accept_all_passing(ctx, run)
    run = pipeline.finalize(ctx, run, compile_fn=fake_compile(pages=2))
    assert not run.result.fits and run.result.dropped
    assert run.result.dropped[0].text  # the human sees what was cut


def test_decisions_after_finalize_reopen_the_run(ctx):
    run = pipeline.start_run(ctx, "JD")
    pipeline.finalize(ctx, run, compile_fn=fake_compile(pages=1))
    pipeline.decide(ctx, run, "p1", "accept")
    assert run.status == "awaiting_review"


def test_finalize_refuses_if_resume_changed(ctx, workspace):
    run = pipeline.start_run(ctx, "JD")
    workspace.resume_path.write_text(ctx.doc.source.replace("Acme Analytics", "Acme Inc"))
    ctx2 = pipeline.load_context(workspace)
    with pytest.raises(pipeline.PipelineError, match="changed"):
        pipeline.finalize(ctx2, run, compile_fn=fake_compile(1))


def test_guards(ctx, workspace):
    with pytest.raises(pipeline.PipelineError, match="empty"):
        pipeline.start_run(ctx, "  ")
    with pytest.raises(pipeline.PipelineError, match="LLM"):
        pipeline.start_run(pipeline.load_context(workspace), "JD")
    run = pipeline.start_run(ctx, "JD")
    pipeline.abort(ctx, run)
    with pytest.raises(pipeline.PipelineError, match="aborted"):
        pipeline.finalize(ctx, run, compile_fn=fake_compile(1))


def test_new_fact_ids_are_persisted(workspace):
    workspace.profile_path.write_text(workspace.profile_path.read_text().replace(
        "general:\n", "general:\n- text: Speaks Spanish\n", 1))
    ctx = pipeline.load_context(workspace)
    assert next(f for f in ctx.profile.facts if f.text == "Speaks Spanish").id == "f13"
    assert "id: f13" in workspace.profile_path.read_text()


# ---------- CLI ----------

def test_review_loop(ctx):
    run = pipeline.start_run(ctx, "JD")
    answers = iter(["a", "x", "r", "a", "e", "Exposed internal tools to LLM agents via an MCP server", "s"])
    out = []
    review_loop(ctx, run, ask=lambda _: next(answers), out=out.append)
    assert [p.status for p in run.proposals] == ["accepted", "rejected", "edited", "pending"]
    assert any("failed verification" in line for line in out)
    assert any("[a]ccept" in line for line in out)  # help shown after the invalid "x"


def test_format_run_mentions_gaps_and_blocked(ctx):
    run = pipeline.start_run(ctx, "JD")
    text = format_run(run, ctx)
    assert "✗ r3 must Kubernetes in production" in text
    assert "(BLOCKED)" in text and "✗ terms" in text
    assert "Coverage 71%" in text
    assert "Tokens:" in text and "analyze" in text  # r1+r2 (must, 2 each) + r4 (nice, 1) of 7


def test_cli_tailor_and_finalize(workspace, monkeypatch, capsys):
    monkeypatch.setattr("bob.cli.get_llm", lambda settings: scripted_llm())
    home = ["--home", str(workspace.root)]
    assert main(["tailor", str(FIXTURES / "jd.txt"), *home]) == 0
    run_id = capsys.readouterr().out.split("bob review ")[-1].strip()
    monkeypatch.setattr("bob.pipeline.compile_tex", fake_compile(1))
    assert main(["finalize", run_id, "--accept-all", *home]) == 0
    assert "Built:" in capsys.readouterr().out
    assert main(["runs", *home]) == 0
    assert run_id in capsys.readouterr().out
    assert main(["show", "no-such-run", *home]) == 1
    assert "no run with id" in capsys.readouterr().err
