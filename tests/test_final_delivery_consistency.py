"""Public deliverables have resolvable figures and honest science boundaries."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "deliverables/report/FINAL_ACADEMIC_REPORT.md"


def test_report_figures_resolve_and_generated_files_exist():
    text = REPORT.read_text()
    figures = re.findall(r"!\[[^]]+\]\(([^)]+)\)", text)
    assert len(figures) >= 5
    assert all((REPORT.parent / name).resolve().is_file() for name in figures)
    for name in ("FINAL_ACADEMIC_REPORT.docx", "FINAL_ACADEMIC_REPORT.pdf"):
        assert (REPORT.parent / name).stat().st_size > 1000
    for name in ("FINAL_PRESENTATION.pptx", "FINAL_PRESENTATION.pdf"):
        assert (ROOT / "deliverables/presentation" / name).stat().st_size > 1000


def test_expanded_editable_deliverables_have_numbered_evidence():
    from docx import Document
    from pptx import Presentation

    document = Document(REPORT.with_suffix(".docx"))
    captions = [paragraph.text for paragraph in document.paragraphs if paragraph.style.name == "Caption"]
    figure_captions = [caption for caption in captions if caption.startswith("Hình ")]
    table_captions = [caption for caption in captions if caption.startswith("Bảng ")]
    source_figures = re.findall(r"!\[[^]]+\]\(([^)]+)\)", REPORT.read_text())
    assert len(figure_captions) == len(source_figures) >= 12
    assert [int(re.match(r"Hình (\d+)", caption).group(1)) for caption in figure_captions] == list(range(1, len(source_figures) + 1))
    assert len(table_captions) >= 4
    assert len(Presentation(ROOT / "deliverables/presentation/FINAL_PRESENTATION.pptx").slides) == 15


def test_report_development_metrics_and_test_status():
    text = REPORT.read_text()
    assert "0,8808" in text
    assert "21,66%" in text
    assert "2025" in text and "SEALED" in text
    assert "người chấm" in text
    assert "không phải" in text


def test_report_values_match_verified_local_results_when_available():
    import json

    closed = ROOT / "data/analysis/finalization_p3_models_20261101_v1/results.json"
    opened = ROOT / "data/analysis/finalization_p3_open_set_20261101_v1/results.json"
    if not closed.exists() or not opened.exists():
        import pytest
        pytest.skip("Private development results absent from clean clone")
    primary = json.loads(closed.read_text())
    open_set = json.loads(opened.read_text())
    text = REPORT.read_text()
    macro = primary["metrics"]["expanded_linear_svm"]["macro_f1"]
    outside = open_set["methods"]["svm_margin"]["evaluation"]["out_false_acceptance_rate"]
    assert f"{macro:.4f}".replace(".", ",") in text
    assert f"{outside * 100:.2f}%".replace(".", ",") in text
    assert primary["validation_selected"] == 681


def test_no_private_artifacts_tracked():
    import subprocess

    files = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    assert not any(name == ".env" or name.startswith("data/raw/") and not name.endswith(".gitkeep")
                   or name.endswith(".joblib") for name in files)
