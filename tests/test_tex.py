import pytest

from bob.tex.editor import EditError, Edits, NewBullet, render
from bob.tex.parser import ParseError, parse
from bob.tex.text import mask_comments, to_latex, to_plain
from tests.conftest import pdflatex_pages

ACME = "experience.data-engineering-intern"


# ---------- text conversion ----------

@pytest.mark.parametrize(
    "latex, plain",
    [
        (r"cut time by 40\%", "cut time by 40%"),
        (r"Globex \& Co.", "Globex & Co."),
        (r"\textbf{Python} and \emph{SQL}", "Python and SQL"),
        (r"\href{https://x.io}{\underline{x.io}}", "x.io"),
        (r"Aug. 2021 -- May 2025", "Aug. 2021 \u2013 May 2025"),
        (r"C\# and React\_UI \$5k", "C# and React_UI $5k"),
        (r"text \vspace{-2pt} more", "text more"),
        ("keep % dropped comment", "keep"),
    ],
)
def test_to_plain(latex, plain):
    assert to_plain(latex) == plain


def test_to_latex_escapes_and_bolds():
    assert to_latex("40% of R&D in C# for $5k_x") == r"40\% of R\&D in C\# for \$5k\_x"
    assert to_latex("Built in **Python** fast") == r"Built in \textbf{Python} fast"
    assert to_latex("a ** b") == r"a ** b"  # unbalanced markers stay literal
    assert to_latex("back\\slash {x}") == r"back\textbackslash{}slash \{x\}"


@pytest.mark.parametrize("plain", ["40% R&D C# $5 a_b {x} ~^", "dash \u2013 and \u2014 here"])
def test_plain_latex_round_trip(plain):
    assert to_plain(to_latex(plain)) == plain


def test_mask_comments_keeps_offsets_and_escaped_percent():
    src = "a 50\\% b % comment\nc"
    masked = mask_comments(src)
    assert len(masked) == len(src)
    assert "50\\% b" in masked and "comment" not in masked and masked.endswith("\nc")


# ---------- parser ----------

def test_parse_structure(resume_src):
    doc = parse(resume_src)
    assert [s.id for s in doc.sections] == [
        "education", "experience", "projects", "leadership", "technical-skills",
    ]
    assert [e.id for e in doc.entries()] == [
        "education.state-university", ACME, "experience.automation-intern",
        "projects.cricketbrain", "leadership.items",
    ]
    acme = doc.entry(ACME)
    assert (acme.title, acme.subtitle) == ("Data Engineering Intern", "Acme Analytics")
    assert doc.entry("projects.cricketbrain").title == "CricketBrain"
    assert doc.entry("education.state-university").bullets == []


def test_parse_bullets(resume_src):
    doc = parse(resume_src)
    acme = doc.entry(ACME)
    assert [b.text for b in acme.bullets] == [
        "Built a multi-agent pipeline in Python that cut report generation time by 40%",
        "Wrote SQL transformations in Snowflake over 2M+ rows of sales data",
        "Exposed internal tools to LLM agents through an MCP server",
    ]
    assert all("Old bullet" not in b.text for b in doc.bullets())  # commented out
    lead = doc.entry("leadership.items").bullets
    assert [b.macro for b in lead] == ["item", "item"]
    assert lead[0].text == "Organized a 200-person campus hackathon & secured $5k in sponsorship"


def test_parse_skills(resume_src):
    doc = parse(resume_src)
    assert {s.category: s.items for s in doc.skill_lines()} == {
        "Languages": ["Python", "SQL", "JavaScript", "C#"],
        "Frameworks": ["FastAPI", "React", "Flask"],
        "Tools": ["Snowflake", "Git", "Docker", "ServiceNow"],
    }
    assert doc.sections[-1].entries == []


def test_unit_spans_tile_each_entry(resume_src):
    doc = parse(resume_src)
    for e in doc.entries():
        for a, b in zip(e.bullets, e.bullets[1:]):
            assert a.unit_span[1] == b.unit_span[0]
        for b in e.bullets:
            assert b.unit_span[0] <= b.content_span[0] < b.content_span[1] <= b.unit_span[1]


def test_parse_errors():
    with pytest.raises(ParseError):
        parse(r"\section{X}")
    with pytest.raises(ParseError):
        parse(r"\begin{document} hi \end{document}")


def test_duplicate_titles_get_unique_ids():
    src = (
        "\\begin{document}\n\\section{Experience}\n"
        "\\resumeSubheading{SWE Intern}{2024}{Acme}{NY}\n\\resumeItemListStart\n\\resumeItem{a}\n\\resumeItemListEnd\n"
        "\\resumeSubheading{SWE Intern}{2023}{Globex}{NY}\n\\resumeItemListStart\n\\resumeItem{b}\n\\resumeItemListEnd\n"
        "\\end{document}\n"
    )
    ids = [e.id for e in parse(src).entries()]
    assert ids == ["experience.swe-intern", "experience.swe-intern-globex"]


def test_item_with_braces_and_same_line_end():
    src = "\\begin{document}\n\\section{Awards}\n\\begin{itemize}\\item{First place} \\item Second \\end{itemize}\n\\end{document}\n"
    doc = parse(src)
    assert [b.text for b in doc.bullets()] == ["First place", "Second"]
    out = render(doc, Edits(orders={"awards.items": ["awards.items.b2", "awards.items.b1"]}))
    assert [b.text for b in parse(out).bullets()] == ["Second", "First place"]


# ---------- editor ----------

def test_render_without_edits_is_byte_identical(resume_src):
    assert render(parse(resume_src)) == resume_src


def test_noop_order_is_byte_identical(resume_src):
    doc = parse(resume_src)
    ids = [b.id for b in doc.entry(ACME).bullets]
    assert render(doc, Edits(orders={ACME: ids}, skills={"technical-skills.tools": doc.skill_lines()[2].items})) == resume_src


def test_rewrite_escapes_and_touches_only_that_bullet(resume_src):
    doc = parse(resume_src)
    out = render(doc, Edits(rewrites={f"{ACME}.b2": "Modeled 2M+ rows in Snowflake & dbt at 99% accuracy"}))
    assert r"Modeled 2M+ rows in Snowflake \& dbt at 99\% accuracy" in out
    new = parse(out)
    assert new.bullet(f"{ACME}.b2").text == "Modeled 2M+ rows in Snowflake & dbt at 99% accuracy"
    assert [b.text for b in new.bullets() if b.id != f"{ACME}.b2"] == [
        b.text for b in doc.bullets() if b.id != f"{ACME}.b2"
    ]
    # everything outside the bullet's text is unchanged
    s, e = doc.bullet(f"{ACME}.b2").content_span
    assert out[:s] == resume_src[:s]
    assert out[len(out) - (len(resume_src) - e):] == resume_src[e:]


def test_drop_add_reorder(resume_src):
    doc = parse(resume_src)
    edits = Edits(
        drops={f"{ACME}.b1"},
        adds={ACME: [NewBullet(f"{ACME}.new1", "Shipped **RAG** search over docs")]},
        orders={ACME: [f"{ACME}.new1", f"{ACME}.b3"]},
    )
    new = parse(render(doc, edits))
    assert [b.text for b in new.entry(ACME).bullets] == [
        "Shipped RAG search over docs",
        "Exposed internal tools to LLM agents through an MCP server",
        "Wrote SQL transformations in Snowflake over 2M+ rows of sales data",
    ]
    assert r"\resumeItem{Shipped \textbf{RAG} search over docs}" in new.source
    # the commented-out line travels with the bullet it preceded
    assert new.source.count("Old bullet that should be ignored") == 1


def test_add_to_plain_item_list(resume_src):
    doc = parse(resume_src)
    out = render(doc, Edits(adds={"leadership.items": [NewBullet("n", "Led ACM chapter")]}))
    assert "    \\item Led ACM chapter\n  \\end{itemize}" in out


def test_skill_line_edit(resume_src):
    doc = parse(resume_src)
    out = render(doc, Edits(skills={"technical-skills.languages": ["SQL", "Python", "C#"]}))
    assert r"\textbf{Languages}{: SQL, Python, C\#}" in out
    assert parse(out).skill_line("technical-skills.languages").items == ["SQL", "Python", "C#"]


def test_editor_rejects_bad_edits(resume_src):
    doc = parse(resume_src)
    with pytest.raises(EditError):
        render(doc, Edits(rewrites={"nope.b1": "x"}))
    with pytest.raises(EditError):
        render(doc, Edits(drops={b.id for b in doc.entry("projects.cricketbrain").bullets}))
    with pytest.raises(EditError):
        render(doc, Edits(adds={"education.state-university": [NewBullet("n", "x")]}))


def test_edited_resume_compiles(resume_src, tmp_path):
    doc = parse(resume_src)
    edits = Edits(
        rewrites={f"{ACME}.b1": "Cut report time 40% with a **Python** multi-agent pipeline (R&D, $0 cost, #1 tool_x)"},
        drops={"projects.cricketbrain.b2"},
        adds={"leadership.items": [NewBullet("n", "Ran 3 workshops ~ 50% women")]},
        orders={ACME: [f"{ACME}.b3"]},
        skills={"technical-skills.tools": ["Docker", "Snowflake"]},
    )
    assert pdflatex_pages(render(doc, edits), tmp_path) == 1


# ---------- templates with unknown heading macros ----------

def test_unknown_heading_macro_still_splits_entries():
    from tests.conftest import FIXTURES

    doc = parse((FIXTURES / "custom_headings.tex").read_text())
    entries = doc.entries()
    assert [(e.title, e.subtitle, len(e.bullets)) for e in entries] == [
        ("Gen Digital \u2013 Software Engineering Intern", "Chennai", 2),
        ("AMD \u2013 Software Development Intern", "Hyderabad", 2),
        ("Blucheetah \u2013 Software Development Intern", "Chennai", 1),
    ]
    assert entries[1].id == "experience.amd-software-development-intern"
    assert "Snowflake" in entries[1].bullets[0].text


def test_reorder_never_moves_bullets_across_non_bullet_content():
    # one list whose bullets are separated by a sub-heading: reordering would carry the heading along
    src = (
        "\\begin{document}\n\\section{Work}\n\\begin{itemize}\n"
        "  \\resumeItem{First}\n  \\textbf{Sub-team}\n  \\resumeItem{Second}\n\\end{itemize}\n\\end{document}\n"
    )
    doc = parse(src)
    entry = doc.entries()[0]
    assert [b.text for b in entry.bullets] == ["First", "Second"]
    out = render(doc, Edits(orders={entry.id: [entry.bullets[1].id, entry.bullets[0].id]}))
    assert out == src  # order request ignored rather than moving the heading


def test_dropping_a_bullet_keeps_the_heading_riding_on_it():
    src = (
        "\\begin{document}\n\\section{Work}\n\\begin{itemize}\n"
        "  \\resumeItem{First}\n  \\textbf{Sub-team}\n  \\resumeItem{Second}\n  \\resumeItem{Third}\n"
        "\\end{itemize}\n\\end{document}\n"
    )
    doc = parse(src)
    out = render(doc, Edits(drops={doc.entries()[0].bullets[1].id}))
    assert "Sub-team" in out and "Second" not in out and "Third" in out


def test_custom_template_edits_compile(tmp_path):
    from tests.conftest import FIXTURES

    doc = parse((FIXTURES / "custom_headings.tex").read_text())
    gen, amd, blu = doc.entries()
    edits = Edits(rewrites={gen.bullets[0].id: "Built **SaaS connectors** for ServiceNow & Adobe Sign API"},
                  orders={amd.id: [amd.bullets[1].id, amd.bullets[0].id]},
                  adds={blu.id: [NewBullet("n", "Handled 30+ concurrent live classes")]})
    out = parse(render(doc, edits))
    assert [b.text for b in out.entries()[1].bullets][0].startswith("Designed Cortex")
    assert pdflatex_pages(render(doc, edits), tmp_path) == 1
