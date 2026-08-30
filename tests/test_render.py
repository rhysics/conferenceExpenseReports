from __future__ import annotations

from expense_report.build import DocumentView, ExpenseView
from expense_report.render import get_environment, latex_escape


def test_latex_escape_handles_special_chars():
    assert latex_escape("100% & fun_time") == r"100\% \& fun\_time"


def test_latex_escape_does_not_double_escape_backslash():
    assert latex_escape("a & b") == r"a \& b"
    assert "\\\\&" not in latex_escape("a & b")


def test_latex_escape_none_is_empty_string():
    assert latex_escape(None) == ""


def _render(expenses, report_currencies=("CHF", "USD"), totals=None, **overrides):
    env = get_environment()
    template = env.get_template("report.tex.jinja")
    if totals is None:
        totals = [0.0] * len(report_currencies)
    context = dict(
        conference_name="PyCon",
        conference_link=None,
        person="Jane Doe",
        research_group=None,
        start_date_display="01 June 2026",
        end_date_display="05 June 2026",
        generated_date="29 August 2026",
        session="Keynote",
        session_link=None,
        grant_acknowledged=True,
        grant_reference=None,
        notes=None,
        extra_notes=None,
        report_currencies=list(report_currencies),
        expenses=expenses,
        totals=totals,
        prepaid_expenses=[],
        prepaid_totals=[0.0] * len(report_currencies),
        all_expenses=expenses,
        additional_documents=[],
        include_signature=False,
    )
    context.update(overrides)
    return template.render(**context)


def test_template_renders_expense_row_and_escapes_name():
    expense = ExpenseView(
        name="Flight & Hotel",
        cost=100.0,
        currency="EUR",
        amounts=[95.0, 108.0],
        note="round trip",
        invoice_path=None,
        invoice_is_pdf=False,
    )
    tex = _render([expense], totals=[95.0, 108.0])

    assert r"Flight \& Hotel" in tex
    assert "95.00" in tex
    assert "108.00" in tex
    assert "conferenceExpenseReports" in tex


def test_template_includes_pdf_invoice_block():
    expense = ExpenseView(
        name="Flight",
        cost=100.0,
        currency="EUR",
        amounts=[95.0, 108.0],
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
        amounts=[95.0, 100.0],
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


def test_us_mode_single_currency_column():
    expense = ExpenseView(
        name="Registration",
        cost=350.0,
        currency="USD",
        amounts=[350.0],
        note=None,
        invoice_path=None,
        invoice_is_pdf=False,
    )
    tex = _render([expense], report_currencies=("USD",), totals=[350.0])

    assert r"\textbf{USD}" in tex
    assert r"\textbf{CHF}" not in tex
    assert tex.count("350.00") >= 2  # once in "Paid", once in the USD column


def test_korea_mode_three_currency_columns():
    expense = ExpenseView(
        name="Flight",
        cost=100.0,
        currency="EUR",
        amounts=[145000.0, 95.0, 108.0],
        note=None,
        invoice_path=None,
        invoice_is_pdf=False,
    )
    tex = _render(
        [expense],
        report_currencies=("KRW", "CHF", "USD"),
        totals=[145000.0, 95.0, 108.0],
    )

    assert r"\textbf{KRW}" in tex
    assert r"\textbf{CHF}" in tex
    assert r"\textbf{USD}" in tex
    assert "145000.00" in tex


def test_kek_mode_two_currency_columns():
    expense = ExpenseView(
        name="Hotel",
        cost=200.0,
        currency="USD",
        amounts=[30000.0, 200.0],
        note=None,
        invoice_path=None,
        invoice_is_pdf=False,
    )
    tex = _render([expense], report_currencies=("JPY", "USD"), totals=[30000.0, 200.0])

    assert r"\textbf{JPY}" in tex
    assert r"\textbf{USD}" in tex
    assert r"\textbf{CHF}" not in tex


def test_template_shows_research_group_when_given():
    tex = _render([], research_group="ATLAS Precision EWK Group")
    assert "ATLAS Precision EWK Group" in tex
    assert "Research Group" in tex


def test_template_omits_research_group_when_absent():
    tex = _render([], research_group=None)
    assert "Research Group" not in tex


def test_template_includes_pdf_additional_document():
    doc = DocumentView(label="Certificate of Attendance", path="extra_0.pdf", is_pdf=True)
    tex = _render([], additional_documents=[doc])

    assert r"\includepdf" in tex
    assert "extra_0.pdf" in tex
    assert "Attachment: Certificate of Attendance" in tex


def test_template_includes_image_additional_document():
    doc = DocumentView(label="Poster Photo", path="extra_0.png", is_pdf=False)
    tex = _render([], additional_documents=[doc])

    assert r"\includegraphics" in tex
    assert "extra_0.png" in tex
    assert "Attachment: Poster Photo" in tex


def test_template_omits_appendix_section_when_no_additional_documents():
    tex = _render([], additional_documents=[])
    assert "Attachment:" not in tex


def test_template_shows_generated_date_in_header():
    tex = _render([], generated_date="29 August 2026")
    assert "Created on 29 August 2026" in tex


def test_template_includes_signature_block_when_enabled():
    tex = _render([], include_signature=True)
    assert "Signature" in tex
    assert "Date" in tex


def test_template_omits_signature_block_by_default():
    tex = _render([], include_signature=False)
    assert "Signature" not in tex


def test_template_omits_prepaid_table_when_none():
    tex = _render([], prepaid_expenses=[])
    assert "Prepaid Expenses" not in tex


def test_template_shows_prepaid_table_with_own_subtotal():
    reimbursable = ExpenseView(
        name="Flight",
        cost=100.0,
        currency="EUR",
        amounts=[95.0, 108.0],
        note=None,
        invoice_path=None,
        invoice_is_pdf=False,
    )
    prepaid = ExpenseView(
        name="Team dinner",
        cost=60.0,
        currency="EUR",
        amounts=[57.0, 64.8],
        note="Paid via department card",
        invoice_path=None,
        invoice_is_pdf=False,
    )
    tex = _render(
        [reimbursable],
        totals=[95.0, 108.0],
        prepaid_expenses=[prepaid],
        prepaid_totals=[57.0, 64.8],
        all_expenses=[reimbursable, prepaid],
    )

    assert "Prepaid Expenses" in tex
    assert "Team dinner" in tex
    assert r"\textbf{Subtotal}" in tex
    assert "57.00" in tex
    assert "64.80" in tex
    # the reimbursable Total must not include the prepaid amount
    assert r"\textbf{95.00}" in tex
    assert r"\textbf{152.00}" not in tex  # 95 + 57, i.e. accidentally merged totals


def test_template_prepaid_invoice_still_appears_in_appendix():
    prepaid = ExpenseView(
        name="Team dinner",
        cost=60.0,
        currency="EUR",
        amounts=[57.0, 64.8],
        note=None,
        invoice_path="invoice_c.pdf",
        invoice_is_pdf=True,
    )
    tex = _render([], prepaid_expenses=[prepaid], all_expenses=[prepaid])
    assert r"\includepdf" in tex
    assert "invoice_c.pdf" in tex
    assert "Invoice: Team dinner" in tex
