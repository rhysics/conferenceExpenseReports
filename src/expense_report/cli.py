from __future__ import annotations

from pathlib import Path

import typer

from .build import BuildError, generate_report, load_yaml
from .validation import validate_report

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Generate LaTeX-based conference expense reports for university reimbursement from a YAML file.",
)


@app.command("validate")
def validate_cmd(
    yaml_file: Path = typer.Argument(..., exists=True, readable=True, help="Path to the report YAML file."),
) -> None:
    """Validate the structure of a report YAML file (offline, no network access)."""
    raw = load_yaml(yaml_file)
    issues = validate_report(raw, yaml_file.resolve())

    if not issues:
        typer.echo("OK: no issues found.")
        raise typer.Exit(code=0)

    for issue in issues:
        typer.echo(str(issue))

    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]
    typer.echo(f"\n{len(errors)} error(s), {len(warnings)} warning(s).")
    raise typer.Exit(code=1 if errors else 0)


@app.command("generate")
def generate_cmd(
    yaml_file: Path = typer.Argument(..., exists=True, readable=True, help="Path to the report YAML file."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output PDF path."),
    keep_build: bool = typer.Option(
        False, "--keep-build", help="Keep the LaTeX build directory (report.tex + logs) for debugging."
    ),
) -> None:
    """Validate, then render and compile the expense report PDF."""
    try:
        output_path = generate_report(yaml_file, output_path=output, keep_build=keep_build)
    except BuildError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Report written to {output_path}")


if __name__ == "__main__":
    app()
