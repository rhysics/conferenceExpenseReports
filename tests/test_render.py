from __future__ import annotations

from expense_report.build import ExpenseView
from expense_report.render import get_environment, latex_escape


def test_latex_escape_handles_special_chars():
    assert latex_escape("100% & fun_time") == r"100\% \& fun\_time"


def test_latex_escape_does_not_double_escape_backslash():
    assert latex_escape("a & b") == r"a \& b"
    assert "\\\\&" not in latex_escape("a & b")


def test_latex_escape_none_is_empty_string():
    assert latex_escape(None) == ""


def _render(expenses, **overrides):
    env = get_environment()
    template = env.get_template("report.tex.jinja")
    context = dict(
        conference_name="PyCon",
        conference_link=None,
        person="Jane Doe",
        start_date_display="01 June 2026",
        end_date_display="05 June 2026",
        session="Keynote",
        session_link=None,
        grant_acknowledged=True,
        grant_reference=None,
        notes=None,
        extra_notes=None,
        expenses=expenses,
        total_chf=0.0,
        total_usd=0.0,
    )
    context.update(overrides)
    return template.render(**context)


def test_template_renders_expense_row_and_escapes_name():
    expense = ExpenseView(
        name="Flight & Hotel",
        cost=100.0,
        currency="EUR",
        chf=95.0,
        usd=108.0,
        note="round trip",
        invoice_path=None,
        invoice_is_pdf=False,
    )
    tex = _render([expense], total_chf=95.0, total_usd=108.0)

    assert r"Flight \& Hotel" in tex
    assert "95.00" in tex
    assert "108.00" in tex
    assert "conferenceExpenseReports" in tex


def test_template_includes_pdf_invoice_block():
    expense = ExpenseView(
        name="Flight",
        cost=100.0,
        currency="EUR",
        chf=95.0,
        usd=108.0,
        note=None,
        invoice_path="invoice_a.pdf",
        invoice_is_pdf=True,
    )
    tex = _render([expense])
    assert r"\includepdf" in tex
    assert "invoice_a.pdf" in tex


def test_template_includes_image_invoice_block():
    expense = ExpenseView(
        name="Registration",
        cost=100.0,
        currency="USD",
        chf=95.0,
        usd=100.0,
        note=None,
        invoice_path="invoice_a.png",
        invoice_is_pdf=False,
    )
    tex = _render([expense])
    assert r"\includegraphics" in tex
    assert "invoice_a.png" in tex


def test_template_omits_link_wrapper_when_no_conference_link():
    tex = _render([], conference_link=None)
    assert r"\href{}" not in tex


def test_template_shows_grant_reference_when_given():
    tex = _render([], grant_reference="SNSF-123456")
    assert "SNSF-123456" in tex
    assert "Grant reference" in tex


def test_template_omits_grant_reference_when_absent():
    tex = _render([], grant_reference=None)
    assert "Grant reference" not in tex
