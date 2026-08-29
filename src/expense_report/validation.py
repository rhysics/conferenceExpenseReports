"""Offline structural validation of a report YAML file.

No network access happens here — FX-rate resolution is a `generate`-time
concern (see fx.py) since it requires calling the Frankfurter API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
ALLOWED_INVOICE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
# Standard strftime directives (https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes).
# strftime() itself doesn't reliably reject unknown directives (it may just pass
# them through literally), so we check against this whitelist ourselves.
VALID_STRFTIME_CODES = set("aAwdbBmyYHIpMSfzZjUWcxXGuV%")

REQUIRED_TOP_FIELDS = [
    "person",
    "conference name",
    "conference start date",
    "conference end date",
    "session",
    "receipts folder",
    "date format",
    "expenses",
]

OPTIONAL_TOP_FIELDS = [
    "conference link",
    "session link",
    "grant acknowledged",
    "grant reference",
    "notes",
    "extra notes",
]

REQUIRED_EXPENSE_FIELDS = ["name", "cost", "purchase date", "currency"]
OPTIONAL_EXPENSE_FIELDS = ["invoice", "note"]

KNOWN_TOP_FIELDS = set(REQUIRED_TOP_FIELDS) | set(OPTIONAL_TOP_FIELDS)
KNOWN_EXPENSE_FIELDS = set(REQUIRED_EXPENSE_FIELDS) | set(OPTIONAL_EXPENSE_FIELDS)


@dataclass
class Issue:
    level: str  # "error" | "warning"
    path: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level.upper()}] {self.path}: {self.message}"


def validate_report(raw: Any, yaml_path: Path) -> list[Issue]:
    issues: list[Issue] = []

    if not isinstance(raw, dict):
        issues.append(Issue("error", "<root>", "top-level YAML content must be a mapping"))
        return issues

    for field in REQUIRED_TOP_FIELDS:
        if field not in raw or raw[field] in (None, ""):
            issues.append(Issue("error", field, "required field is missing or empty"))

    for field in raw:
        if field not in KNOWN_TOP_FIELDS:
            issues.append(Issue("warning", field, "unrecognized field (typo?)"))

    start = _check_date(raw.get("conference start date"), "conference start date", issues)
    end = _check_date(raw.get("conference end date"), "conference end date", issues)
    if start is not None and end is not None and end < start:
        issues.append(Issue("error", "conference end date", "is before conference start date"))

    date_format = raw.get("date format")
    if date_format is not None and not isinstance(date_format, str):
        issues.append(Issue("error", "date format", "must be a string strftime pattern, e.g. '%d %B %Y'"))
    elif isinstance(date_format, str):
        _validate_strftime_pattern(date_format, issues)

    grant_acknowledged = raw.get("grant acknowledged")
    if grant_acknowledged is not None and not isinstance(grant_acknowledged, bool):
        issues.append(
            Issue("warning", "grant acknowledged", "expected a boolean (yes/no); will be treated as truthy")
        )

    grant_reference = raw.get("grant reference")
    if grant_reference is not None and not isinstance(grant_reference, str):
        issues.append(Issue("error", "grant reference", "must be a string"))
    if grant_acknowledged is True and not grant_reference:
        issues.append(
            Issue("warning", "grant reference", "grant acknowledged is true but no grant reference was given")
        )
    if grant_reference and not grant_acknowledged:
        issues.append(
            Issue("warning", "grant reference", "given but 'grant acknowledged' is not true")
        )

    receipts_dir = None
    receipts_folder = raw.get("receipts folder")
    if isinstance(receipts_folder, str) and receipts_folder:
        receipts_dir = (yaml_path.parent / receipts_folder).expanduser()
        if not receipts_dir.is_dir():
            issues.append(Issue("error", "receipts folder", f"directory not found: {receipts_dir}"))
    elif receipts_folder is not None:
        issues.append(Issue("error", "receipts folder", "must be a string path"))

    expenses = raw.get("expenses")
    if expenses is not None:
        if not isinstance(expenses, dict) or not expenses:
            issues.append(Issue("error", "expenses", "must be a non-empty mapping of expense entries"))
        else:
            for key, entry in expenses.items():
                _validate_expense(key, entry, receipts_dir, issues)

    return issues


def _validate_strftime_pattern(fmt: str, issues: list[Issue]) -> None:
    i = 0
    while i < len(fmt):
        if fmt[i] != "%":
            i += 1
            continue
        if i + 1 >= len(fmt):
            issues.append(Issue("error", "date format", "trailing '%' with no directive code"))
            break
        code = fmt[i + 1]
        if code not in VALID_STRFTIME_CODES:
            issues.append(Issue("error", "date format", f"unknown strftime directive '%{code}'"))
        i += 2


def _check_date(value: Any, path: str, issues: list[Issue]) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    issues.append(Issue("error", path, f"must be a date (YAML date, e.g. 2026-06-01), got {value!r}"))
    return None


def _validate_expense(key: Any, entry: Any, receipts_dir: Path | None, issues: list[Issue]) -> None:
    prefix = f"expenses.{key}"
    if not isinstance(entry, dict):
        issues.append(Issue("error", prefix, "must be a mapping"))
        return

    for field in REQUIRED_EXPENSE_FIELDS:
        if field not in entry or entry[field] in (None, ""):
            issues.append(Issue("error", f"{prefix}.{field}", "required field is missing or empty"))

    for field in entry:
        if field not in KNOWN_EXPENSE_FIELDS:
            issues.append(Issue("warning", f"{prefix}.{field}", "unrecognized field (typo?)"))

    cost = entry.get("cost")
    if cost is not None and not isinstance(cost, (int, float)):
        issues.append(Issue("error", f"{prefix}.cost", f"must be a number, got {cost!r}"))
    elif isinstance(cost, (int, float)) and cost <= 0:
        issues.append(Issue("error", f"{prefix}.cost", "must be greater than zero"))

    _check_date(entry.get("purchase date"), f"{prefix}.purchase date", issues)

    currency = entry.get("currency")
    if isinstance(currency, str):
        if not CURRENCY_RE.match(currency.upper()):
            issues.append(
                Issue("error", f"{prefix}.currency", f"must be a 3-letter ISO 4217 code, got {currency!r}")
            )
    elif currency is not None:
        issues.append(Issue("error", f"{prefix}.currency", "must be a string currency code"))

    invoice = entry.get("invoice")
    if invoice is not None:
        if not isinstance(invoice, str):
            issues.append(Issue("error", f"{prefix}.invoice", "must be a string filename"))
        else:
            ext = Path(invoice).suffix.lower()
            if ext not in ALLOWED_INVOICE_EXTENSIONS:
                issues.append(
                    Issue(
                        "error",
                        f"{prefix}.invoice",
                        f"unsupported file type {ext!r}; allowed: {sorted(ALLOWED_INVOICE_EXTENSIONS)}",
                    )
                )
            if receipts_dir is not None and not (receipts_dir / invoice).is_file():
                issues.append(Issue("error", f"{prefix}.invoice", f"file not found in receipts folder: {invoice}"))
