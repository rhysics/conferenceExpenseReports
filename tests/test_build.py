from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from expense_report.build import generate_report

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

requires_xelatex = pytest.mark.skipif(shutil.which("xelatex") is None, reason="xelatex not found on PATH")


def _mock_response(rates: dict) -> Mock:
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json.return_value = {"rates": rates}
    return resp


@requires_xelatex
def test_generate_report_end_to_end(tmp_path):
    work_dir = tmp_path / "report"
    shutil.copytree(EXAMPLES_DIR, work_dir)
    yaml_path = work_dir / "example_report.yaml"

    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"CHF": 0.95, "USD": 1.08})
        output_path = generate_report(yaml_path)

    assert output_path.is_file()
    assert output_path.suffix == ".pdf"
    assert output_path.stat().st_size > 1000
    assert (work_dir / ".fx_cache.json").is_file()


@requires_xelatex
def test_generate_report_keep_build_preserves_tex_source(tmp_path):
    work_dir = tmp_path / "report"
    shutil.copytree(EXAMPLES_DIR, work_dir)
    yaml_path = work_dir / "example_report.yaml"

    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"CHF": 0.95, "USD": 1.08})
        generate_report(yaml_path, keep_build=True)

    build_dirs = list(work_dir.glob("*-build"))
    assert len(build_dirs) == 1
    assert (build_dirs[0] / "report.tex").is_file()


@requires_xelatex
def test_generate_report_with_custom_report_currencies(tmp_path):
    work_dir = tmp_path / "report"
    shutil.copytree(EXAMPLES_DIR, work_dir)
    yaml_path = work_dir / "example_report.yaml"

    data = yaml.safe_load(yaml_path.read_text())
    data["report currencies"] = ["USD"]
    yaml_path.write_text(yaml.dump(data, sort_keys=False))

    with patch("expense_report.fx.requests.get") as mock_get:
        mock_get.return_value = _mock_response({"USD": 1.08})
        generate_report(yaml_path, keep_build=True)

    build_dirs = list(work_dir.glob("*-build"))
    tex_source = (build_dirs[0] / "report.tex").read_text()
    assert r"\textbf{USD}" in tex_source
    assert r"\textbf{CHF}" not in tex_source
