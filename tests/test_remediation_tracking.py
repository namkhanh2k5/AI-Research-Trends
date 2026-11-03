"""The independent audit's twelve findings remain individually traceable."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_all_baseline_issues_have_valid_status_and_evidence_paths():
    tracker = json.loads((ROOT / "reports/FINALIZATION_P4_1_AUDIT_ISSUES.json").read_text())
    assert [issue["id"] for issue in tracker["issues"]] == [f"AUD-{number:02d}" for number in range(1, 13)]
    for issue in tracker["issues"]:
        assert issue["status"] in tracker["status_terms"]
        assert issue["root_cause"] and issue["fix"] and issue["verification"]
        assert all((ROOT / path).exists() for path in issue["files"])
    report = (ROOT / "reports/FINALIZATION_P4_REMEDIATION_REPORT.md").read_text()
    assert all(issue["id"] in report for issue in tracker["issues"])
