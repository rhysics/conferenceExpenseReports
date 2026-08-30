from __future__ import annotations

from datetime import date
from pathlib import Path

from expense_report.validation import validate_report


def _base_raw(tmp_path: Path) -> dict:
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    (receipts / "flight.pdf").write_bytes(b"%PDF-1.4\n")
    (receipts / "certificate.pdf").write_bytes(b"%PDF-1.4\n")
    return {
        "person": "Jane Doe",
        "conference name": "PyCon",
        "conference start date": date(2026, 6, 1),
        "conference end date": date(2026, 6, 5),
        "session": "Keynote",
        "receipts folder": "receipts",
        "date format": "%d %B %Y",
        "grant acknowledged": True,
        "expenses": {
            "a": {
                "name": "Flight",
                "cost": 450.0,
                "purchase date": date(2026, 5, 20),
                "currency": "EUR",
                "invoice": "flight.pdf",
            }
        },
    }


def _errors(issues):
    return [i for i in issues if i.level == "error"]


def test_valid_report_has_no_errors(tmp_path):
    raw = _base_raw(tmp_path)
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_missing_required_field(tmp_path):
    raw = _base_raw(tmp_path)
    del raw["session"]
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "session" and i.level == "error" for i in issues)


def test_end_before_start(tmp_path):
    raw = _base_raw(tmp_path)
    raw["conference end date"] = date(2026, 5, 1)
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any("before" in i.message for i in _errors(issues))


def test_date_given_as_string_is_an_error(tmp_path):
    raw = _base_raw(tmp_path)
    raw["conference start date"] = "2026-06-01"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "conference start date" for i in _errors(issues))


def test_bad_date_format_string(tmp_path):
    raw = _base_raw(tmp_path)
    raw["date format"] = "%Q"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "date format" for i in _errors(issues))


def test_bad_currency_code(tmp_path):
    raw = _base_raw(tmp_path)
    raw["expenses"]["a"]["currency"] = "euros"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "expenses.a.currency" for i in _errors(issues))


def test_non_positive_cost(tmp_path):
    raw = _base_raw(tmp_path)
    raw["expenses"]["a"]["cost"] = 0
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "expenses.a.cost" for i in _errors(issues))


def test_prepaid_true_is_valid(tmp_path):
    raw = _base_raw(tmp_path)
    raw["expenses"]["a"]["prepaid"] = True
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_prepaid_omitted_is_fine(tmp_path):
    raw = _base_raw(tmp_path)
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_prepaid_non_boolean_warns_not_errors(tmp_path):
    raw = _base_raw(tmp_path)
    raw["expenses"]["a"]["prepaid"] = "yes"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "expenses.a.prepaid" and i.level == "warning" for i in issues)
    assert _errors(issues) == []


def test_missing_invoice_file(tmp_path):
    raw = _base_raw(tmp_path)
    raw["expenses"]["a"]["invoice"] = "missing.pdf"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any("not found" in i.message for i in _errors(issues))


def test_unsupported_invoice_extension(tmp_path):
    raw = _base_raw(tmp_path)
    (tmp_path / "receipts" / "flight.docx").write_bytes(b"not really a docx")
    raw["expenses"]["a"]["invoice"] = "flight.docx"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any("unsupported file type" in i.message for i in _errors(issues))


def test_missing_receipts_folder(tmp_path):
    raw = _base_raw(tmp_path)
    raw["receipts folder"] = "does-not-exist"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "receipts folder" for i in _errors(issues))


def test_empty_expenses_is_an_error(tmp_path):
    raw = _base_raw(tmp_path)
    raw["expenses"] = {}
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "expenses" for i in _errors(issues))


def test_grant_acknowledged_without_reference_warns(tmp_path):
    raw = _base_raw(tmp_path)
    raw["grant acknowledged"] = True
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "grant reference" and i.level == "warning" for i in issues)
    assert _errors(issues) == []


def test_grant_reference_without_acknowledged_warns(tmp_path):
    raw = _base_raw(tmp_path)
    raw["grant acknowledged"] = False
    raw["grant reference"] = "SNSF-123456"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "grant reference" and i.level == "warning" for i in issues)


def test_grant_acknowledged_with_reference_is_clean(tmp_path):
    raw = _base_raw(tmp_path)
    raw["grant acknowledged"] = True
    raw["grant reference"] = "SNSF-123456"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert issues == []


def test_grant_reference_must_be_a_string(tmp_path):
    raw = _base_raw(tmp_path)
    raw["grant acknowledged"] = True
    raw["grant reference"] = 123456
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "grant reference" and i.level == "error" for i in issues)


def test_report_currencies_omitted_is_fine(tmp_path):
    raw = _base_raw(tmp_path)
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_report_currencies_single_currency_is_valid(tmp_path):
    raw = _base_raw(tmp_path)
    raw["report currencies"] = ["USD"]
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_report_currencies_multiple_is_valid(tmp_path):
    raw = _base_raw(tmp_path)
    raw["report currencies"] = ["KRW", "CHF", "USD"]
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_include_signature_true_is_valid(tmp_path):
    raw = _base_raw(tmp_path)
    raw["include signature"] = True
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_include_signature_omitted_is_fine(tmp_path):
    raw = _base_raw(tmp_path)
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_include_signature_non_boolean_warns_not_errors(tmp_path):
    raw = _base_raw(tmp_path)
    raw["include signature"] = "yes"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "include signature" and i.level == "warning" for i in issues)
    assert _errors(issues) == []


def test_report_currencies_must_be_a_list(tmp_path):
    raw = _base_raw(tmp_path)
    raw["report currencies"] = "USD"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "report currencies" for i in _errors(issues))


def test_report_currencies_empty_list_is_an_error(tmp_path):
    raw = _base_raw(tmp_path)
    raw["report currencies"] = []
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "report currencies" for i in _errors(issues))


def test_report_currencies_bad_code_is_an_error(tmp_path):
    raw = _base_raw(tmp_path)
    raw["report currencies"] = ["USD", "wons"]
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "report currencies[1]" for i in _errors(issues))


def test_research_group_is_optional_and_valid_as_a_string(tmp_path):
    raw = _base_raw(tmp_path)
    raw["research group"] = "ATLAS Precision EWK Group"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_research_group_must_be_a_string(tmp_path):
    raw = _base_raw(tmp_path)
    raw["research group"] = 123
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "research group" for i in _errors(issues))


def test_additional_documents_as_plain_filenames(tmp_path):
    raw = _base_raw(tmp_path)
    raw["additional documents"] = ["certificate.pdf"]
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_additional_documents_as_mappings_with_label(tmp_path):
    raw = _base_raw(tmp_path)
    raw["additional documents"] = [{"file": "certificate.pdf", "label": "Certificate of Attendance"}]
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert _errors(issues) == []


def test_additional_documents_missing_file_is_an_error(tmp_path):
    raw = _base_raw(tmp_path)
    raw["additional documents"] = ["missing.pdf"]
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any("not found" in i.message for i in _errors(issues))


def test_additional_documents_bad_extension_is_an_error(tmp_path):
    raw = _base_raw(tmp_path)
    (tmp_path / "receipts" / "notes.docx").write_bytes(b"not a real docx")
    raw["additional documents"] = ["notes.docx"]
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any("unsupported file type" in i.message for i in _errors(issues))


def test_additional_documents_mapping_missing_file_key_is_an_error(tmp_path):
    raw = _base_raw(tmp_path)
    raw["additional documents"] = [{"label": "Certificate of Attendance"}]
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "additional documents[0].file" for i in _errors(issues))


def test_additional_documents_must_be_a_list(tmp_path):
    raw = _base_raw(tmp_path)
    raw["additional documents"] = "certificate.pdf"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "additional documents" for i in _errors(issues))


def test_unrecognized_field_warns_not_errors(tmp_path):
    raw = _base_raw(tmp_path)
    raw["speling mistake"] = "oops"
    issues = validate_report(raw, tmp_path / "report.yaml")
    assert any(i.path == "speling mistake" and i.level == "warning" for i in issues)
    assert _errors(issues) == []
