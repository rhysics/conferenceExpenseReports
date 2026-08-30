"""Orchestrates: validate -> resolve FX rates -> render LaTeX -> compile PDF."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from .fx import FxCache, FxError, get_rates
from .render import get_environment
from .schema import parse_report
from .validation import validate_report

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class BuildError(RuntimeError):
    pass


@dataclass
class ExpenseView:
    name: str
    cost: float
    currency: str
    amounts: list[float]
    note: str | None
    invoice_path: str | None
    invoice_is_pdf: bool


@dataclass
class DocumentView:
    label: str
    path: str
    is_pdf: bool


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "conference"


def _humanize_filename(stem: str) -> str:
    return re.sub(r"[_-]+", " ", stem).strip().title()


def generate_report(
    yaml_path: Path,
    output_path: Path | None = None,
    keep_build: bool = False,
) -> Path:
    yaml_path = Path(yaml_path).resolve()
    raw = load_yaml(yaml_path)

    issues = validate_report(raw, yaml_path)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        raise BuildError("YAML failed validation:\n" + "\n".join(str(i) for i in errors))

    report = parse_report(raw, yaml_path)

    if output_path is None:
        output_path = yaml_path.parent / f"{slugify(report.conference_name)}-expense-report.pdf"
    output_path = Path(output_path).resolve()

    cache = FxCache(yaml_path.parent / ".fx_cache.json")

    if keep_build:
        build_dir = yaml_path.parent / f"{slugify(report.conference_name)}-build"
        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(parents=True)
        produced_pdf = _build(report, build_dir, cache)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(produced_pdf, output_path)
    else:
        with TemporaryDirectory(prefix="expense_report_") as tmp:
            build_dir = Path(tmp)
            produced_pdf = _build(report, build_dir, cache)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(produced_pdf, output_path)

    return output_path


def _build(report, build_dir: Path, cache: FxCache) -> Path:
    report_currencies = report.report_currencies
    all_expense_views: list[ExpenseView] = []
    reimbursable_views: list[ExpenseView] = []
    prepaid_views: list[ExpenseView] = []
    totals = [0.0] * len(report_currencies)
    prepaid_totals = [0.0] * len(report_currencies)
    warnings: list[str] = []

    for expense in report.expenses:
        try:
            rates, used_date = get_rates(expense.purchase_date, expense.currency, report_currencies, cache)
        except FxError as exc:
            raise BuildError(f"expense '{expense.name}': {exc}") from exc

        if used_date != expense.purchase_date:
            warnings.append(
                f"expense '{expense.name}': no FX rate for {expense.purchase_date}, used {used_date} instead"
            )

        amounts = [expense.cost * rates[code] for code in report_currencies]

        invoice_path = None
        invoice_is_pdf = False
        if expense.invoice:
            src = report.receipts_folder / expense.invoice
            ext = src.suffix.lower()
            invoice_is_pdf = ext == ".pdf"
            dest_name = f"invoice_{expense.key}{ext}"
            shutil.copy(src, build_dir / dest_name)
            invoice_path = dest_name

        view = ExpenseView(
            name=expense.name,
            cost=expense.cost,
            currency=expense.currency,
            amounts=amounts,
            note=expense.note,
            invoice_path=invoice_path,
            invoice_is_pdf=invoice_is_pdf,
        )
        all_expense_views.append(view)

        if expense.prepaid:
            prepaid_views.append(view)
            prepaid_totals = [t + a for t, a in zip(prepaid_totals, amounts, strict=True)]
        else:
            reimbursable_views.append(view)
            totals = [t + a for t, a in zip(totals, amounts, strict=True)]

    document_views: list[DocumentView] = []
    for i, doc in enumerate(report.additional_documents):
        src = report.receipts_folder / doc.file
        ext = src.suffix.lower()
        dest_name = f"extra_{i}{ext}"
        shutil.copy(src, build_dir / dest_name)
        document_views.append(
            DocumentView(
                label=doc.label or _humanize_filename(src.stem),
                path=dest_name,
                is_pdf=ext == ".pdf",
            )
        )

    env = get_environment()
    template = env.get_template("report.tex.jinja")
    tex_source = template.render(
        conference_name=report.conference_name,
        conference_link=report.conference_link,
        person=report.person,
        research_group=report.research_group,
        start_date_display=report.conference_start_date.strftime(report.date_format),
        end_date_display=report.conference_end_date.strftime(report.date_format),
        generated_date=date.today().strftime(report.date_format),
        session=report.session,
        session_link=report.session_link,
        grant_acknowledged=report.grant_acknowledged,
        grant_reference=report.grant_reference,
        notes=report.notes,
        extra_notes=report.extra_notes,
        report_currencies=report_currencies,
        expenses=reimbursable_views,
        totals=totals,
        prepaid_expenses=prepaid_views,
        prepaid_totals=prepaid_totals,
        all_expenses=all_expense_views,
        additional_documents=document_views,
        include_signature=report.include_signature,
    )

    tex_path = build_dir / "report.tex"
    tex_path.write_text(tex_source, encoding="utf-8")

    _run_xelatex(tex_path, build_dir)
    _run_xelatex(tex_path, build_dir)  # second pass resolves lastpage/hyperref refs

    produced_pdf = build_dir / "report.pdf"
    if not produced_pdf.is_file():
        raise BuildError("xelatex did not produce a PDF (see build log)")

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    return produced_pdf


def _run_xelatex(tex_path: Path, cwd: Path) -> None:
    xelatex = shutil.which("xelatex")
    if xelatex is None:
        raise BuildError("xelatex not found on PATH; please install a TeX distribution (e.g. TeX Live, MacTeX)")

    result = subprocess.run(
        [xelatex, "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log_path = tex_path.with_suffix(".log")
        tail = ""
        if log_path.is_file():
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            tail = "\n".join(lines[-40:])
        raise BuildError(f"xelatex failed (exit {result.returncode}):\n{tail}")
