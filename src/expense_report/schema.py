"""Typed representation of a report YAML file.

`parse_report` assumes the raw dict has already passed
`validation.validate_report` with no errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class Expense:
    key: str
    name: str
    cost: float
    purchase_date: date
    currency: str
    invoice: str | None = None
    note: str | None = None


@dataclass
class Report:
    person: str
    conference_name: str
    conference_start_date: date
    conference_end_date: date
    session: str
    receipts_folder: Path
    date_format: str
    expenses: list[Expense]
    conference_link: str | None = None
    session_link: str | None = None
    grant_acknowledged: bool = False
    grant_reference: str | None = None
    notes: str | None = None
    extra_notes: str | None = None


def parse_report(raw: dict, yaml_path: Path) -> Report:
    receipts_folder = (yaml_path.parent / raw["receipts folder"]).expanduser().resolve()

    expenses = [
        Expense(
            key=str(key),
            name=entry["name"],
            cost=float(entry["cost"]),
            purchase_date=entry["purchase date"],
            currency=entry["currency"].upper(),
            invoice=entry.get("invoice"),
            note=entry.get("note"),
        )
        for key, entry in raw["expenses"].items()
    ]

    return Report(
        person=raw["person"],
        conference_name=raw["conference name"],
        conference_start_date=raw["conference start date"],
        conference_end_date=raw["conference end date"],
        session=raw["session"],
        receipts_folder=receipts_folder,
        date_format=raw["date format"],
        expenses=expenses,
        conference_link=raw.get("conference link"),
        session_link=raw.get("session link"),
        grant_acknowledged=bool(raw.get("grant acknowledged", False)),
        grant_reference=raw.get("grant reference"),
        notes=raw.get("notes"),
        extra_notes=raw.get("extra notes"),
    )
