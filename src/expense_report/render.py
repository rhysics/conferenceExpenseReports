"""Jinja2 setup for rendering the LaTeX report template.

Jinja's default `{{ }}` / `{% %}` / `{# #}` delimiters collide with LaTeX's
own use of `{`, `}` and `%`, so this environment uses LaTeX-friendly
delimiters instead (a well-known trick, see e.g. the classic "LaTeX with
Jinja2" recipe): `(( ))` for variables, `((* *))` for blocks, `((# #))` for
comments.
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent / "templates"

_LATEX_SPECIAL_CHARS = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}
_LATEX_RE = re.compile("|".join(re.escape(k) for k in _LATEX_SPECIAL_CHARS))


def latex_escape(value: object) -> str:
    """Escape LaTeX special characters in a single left-to-right pass.

    A single regex substitution (rather than sequential str.replace calls)
    avoids double-escaping characters introduced by earlier replacements
    (e.g. the backslash in `\\&`).
    """
    if value is None:
        return ""
    text = str(value)
    return _LATEX_RE.sub(lambda m: _LATEX_SPECIAL_CHARS[m.group()], text)


def get_environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        variable_start_string="((",
        variable_end_string="))",
        block_start_string="((*",
        block_end_string="*))",
        comment_start_string="((#",
        comment_end_string="#))",
    )
    env.filters["latex"] = latex_escape
    return env
