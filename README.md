# conferenceExpenseReports

Generate a LaTeX-typeset conference expense report — a summary page followed
by every invoice — for submission to a university reimbursement process,
from a single YAML file.

## Requirements

- Python 3.10+
- A TeX distribution providing `xelatex` on `PATH` (e.g. MacTeX, TeX Live),
  with the (standard) `pdfpages`, `longtable`, `booktabs`, `hyperref`,
  `fancyhdr`, `lastpage` and `grffile` packages available.

## Installation

```sh
pip install -e .
```

This installs the `expense-report` CLI.

## Usage

```sh
expense-report validate report.yaml
expense-report generate report.yaml -o report.pdf
```

- `validate` checks the YAML structure, required fields, dates, currency
  codes, and that every referenced invoice file exists in the receipts
  folder. It runs fully offline.
- `generate` re-validates, looks up historical CHF/USD exchange rates for
  each expense's purchase date via the [Frankfurter API](https://frankfurter.dev)
  (ECB reference rates), and compiles the final PDF. Rates are cached in a
  `.fx_cache.json` file next to the YAML file so repeat runs don't re-hit the
  network. Pass `--keep-build` to keep the generated `.tex` source and
  `xelatex` log for debugging.

See [`examples/example_report.yaml`](examples/example_report.yaml) for a
complete example.

## YAML schema

| Field | Required | Notes |
|---|---|---|
| `person` | yes | Name of the person submitting the claim |
| `conference name` | yes | |
| `conference link` | no | Rendered as a hyperlink on the conference name |
| `conference start date` | yes | Plain YAML date, e.g. `2026-06-01` |
| `conference end date` | yes | Plain YAML date |
| `session` | yes | The talk/session attended or given |
| `session link` | no | Rendered as a hyperlink on the session |
| `grant acknowledged` | no | `true`/`false` |
| `grant reference` | no | Grant number/name; shown only when given. A warning is raised if `grant acknowledged` is true but this is missing (or vice versa) |
| `notes` | no | Free text shown near the top of the report |
| `receipts folder` | yes | Path (relative to the YAML file) containing invoice files |
| `date format` | yes | A `strftime` pattern controlling how dates are *displayed*, e.g. `"%d %B %Y"` |
| `expenses` | yes | Mapping of arbitrary keys to expense entries (see below) |
| `report currencies` | no | List of ISO 4217 codes controlling which converted-amount columns appear in the summary table, and in what order. Defaults to `[CHF, USD]`. See [Report currency modes](#report-currency-modes) below |
| `extra notes` | no | Free text shown after the summary table |

Each entry under `expenses` (key is arbitrary, e.g. `a`, `b`, `flight`, ...):

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Shown in the summary table |
| `cost` | yes | Numeric, in the original currency paid |
| `purchase date` | yes | Plain YAML date; used for the FX lookup |
| `currency` | yes | 3-letter ISO 4217 code, e.g. `EUR`, `USD`, `CHF` |
| `invoice` | no | Exact filename of the receipt inside `receipts folder`. Supported types: `.pdf`, `.png`, `.jpg`, `.jpeg`. Omit if there's no receipt for this line item. |
| `note` | no | Shown in the summary table's Notes column |

Dates are given as plain YAML dates (not strings) so parsing is unambiguous;
`date format` only controls how they're *displayed* in the PDF.

### Report currency modes

The summary table always shows an **Expense** column, a **Paid** column (the
original amount and currency for each expense), and a **Notes** column. In
between, `report currencies` controls which converted-amount columns appear
and in what order — one column per currency listed, each converted using the
exchange rate for that expense's purchase date. Some useful configurations:

| Scenario | `report currencies:` | Columns |
|---|---|---|
| Default (omit the key) | *(none — defaults to `[CHF, USD]`)* | Expense, Paid, CHF, USD, Notes |
| US at CERN reimbursement | `[CHF, USD]` | Expense, Paid, USD, Notes |
| US-only reimbursement | `[USD]` | Expense, Paid, USD, Notes |
| Korea-affiliated group | `[KRW, CHF, USD]` | Expense, Paid, KRW, CHF, USD, Notes |
| European group at CERN | `[CHF, EUR]` | Expense, Paid, CHF, EUR, Notes |

Any other Frankfurter-supported ISO 4217 code works too (e.g. `[GBP, USD]`
for a UK grant) — this isn't a fixed set of "modes," just a list you can
tailor per report.

### Common currency codes

`currency` accepts any 3-letter ISO 4217 code supported by the
[Frankfurter API](https://frankfurter.dev). Some common examples listed below; see the API docs for a full list.

| Code | Currency |
|---|---|
| `USD` | US Dollar |
| `CHF` | Swiss Franc |
| `EUR` | Euro |
| `GBP` | British Pound |
| `JPY` | Japanese Yen |
| `CNY` | Chinese Yuan |
| `CAD` | Canadian Dollar |
| `INR` | Indian Rupee |
| `KRW` | South Korean Won |
| `AUD` | Australian Dollar |
| `SEK` | Swedish Krona |
| `PLN` | Polish Złoty |
| `CZK` | Czech Koruna |

## Output

Page 1 is the conference summary: conference/session details, an expense
table (Expense | Paid | one column per `report currencies` entry | Notes)
with a totals row, a note on the FX methodology (European Central Bank
reference rates via the Frankfurter API, linked), and a footer crediting this
project. Every expense with an `invoice` gets its receipt appended
afterward, one per page, labeled with the expense name so it's easy to match
back to the summary table.

## Development

```sh
pip install -e ".[dev]"
pre-commit install
```

This runs [ruff](https://docs.astral.sh/ruff/) (lint + format) and basic file
hygiene checks (trailing whitespace, YAML/TOML syntax, no accidental
large-file or merge-conflict commits) on every `git commit`. Run it manually
against everything with:

```sh
pre-commit run --all-files
```
