"""One-time, deterministic Git-aware move/rebase of research Markdown files.

Run from repository root after the Phase 6 artifact migration. The source
documents are only moved; Markdown relative links are adjusted mechanically.
Protected manifest-hashed protocols remain in place and byte-unchanged.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
PROTOCOLS = {
    "FINALIZATION_P2_HUMAN_REVIEW.md",
    "FINALIZATION_P2_WEB_DATA_CONTRACT.md",
    "FINALIZATION_P3_FROZEN_EVALUATION_PROTOCOL.md",
    "FINALIZATION_P3_ML_EXPERIMENT_PROTOCOL.md",
    "PHASE5_RQ5_PLAN.md",
    "PHASE6B_DECISION_CRITERIA.md",
    "PHASE6B_EXPANDED_CATALOGUE_PROTOCOL.md",
    "PHASE6B_HUMAN_REVIEW_INSTRUCTIONS.md",
    "PHASE6_HUMAN_ANNOTATION_GUIDELINES.md",
    "PHASE6_TOPIC_SELECTION_PROTOCOL.md",
}


def report_destination(name: str) -> str:
    if name.startswith("PHASE6") or name == "FINALIZATION_P2_RQ6_TOPIC_LABEL_ANALYSIS.md":
        return "reports/phase6/" + name
    if name.startswith("PHASE5"):
        return "reports/research/phase5/" + name
    if name.startswith("PHASE4"):
        return "reports/research/phase4/" + name
    if name.startswith("PHASE3"):
        return "reports/research/phase3/" + name
    if name.startswith("PHASE2"):
        return "reports/research/phase2/" + name
    if name in {"PRE_PHASE2_REVIEW.md", "data_feasibility.md", "topic_discovery.md"}:
        return "reports/research/phase1/" + name
    if name.startswith("FINALIZATION_P1"):
        return "reports/machine_learning/data_expansion/" + name
    if name.startswith("FINALIZATION_P2"):
        return "reports/machine_learning/integration/" + name
    if name.startswith("FINALIZATION_P3"):
        return "reports/machine_learning/" + name
    if name.startswith("FINALIZATION_P4") or name == "PAPER_DISCOVERY_TECHNICAL_EVALUATION.md":
        return "reports/application/" + name
    if name in {"FINAL_INDEPENDENT_PROJECT_AUDIT.md", "REORGANIZATION_INVENTORY.md", "REPOSITORY_REORGANIZATION_REPORT.md"}:
        return "reports/audit/" + name
    raise ValueError(f"Unclassified report: {name}")


def main() -> None:
    moves: dict[Path, Path] = {}
    for name in PROTOCOLS:
        moves[Path("docs") / name] = Path("docs/protocols") / name
    moves[Path("docs/PHASE4_PRESENTATION_BRIEF.md")] = Path("docs/presentation/PHASE4_PRESENTATION_BRIEF.md")
    moves[Path("docs/REPOSITORY_CLEANUP.md")] = Path("docs/archive/REPOSITORY_CLEANUP.md")
    for old in sorted((ROOT / "reports").glob("*.md")):
        if old.name == "README.md":
            continue
        source = old.relative_to(ROOT)
        moves[source] = Path(report_destination(old.name))
    aliases = {
        Path("data/analysis/phase6_topic_pilot_20261028_v12"): Path("data/analysis/phase6/pilot"),
        Path("data/analysis/phase6a_reproduction_20261028_phase6b"): Path("data/analysis/phase6/pilot"),
        Path("data/analysis/phase6b_topic_metadata_20261028_v1"): Path("data/analysis/phase6/metadata"),
        Path("data/analysis/phase6b_topic_validation_20261028_v3"): Path("data/analysis/phase6/validation"),
        Path("data/analysis/finalization_p2_rq6_20261101_v3"): Path("data/analysis/phase6/topic_analysis"),
    }

    def relocate(path: Path) -> Path:
        if path in moves:
            return moves[path]
        for old, new in aliases.items():
            if path == old or old in path.parents:
                return new / path.relative_to(old)
        return path

    for old, new in moves.items():
        source, target = ROOT / old, ROOT / new
        if not source.is_file() or target.exists():
            raise FileExistsError(f"Refusing ambiguous move: {old} -> {new}")
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "mv", str(old), str(new)], cwd=ROOT, check=True)

    link = re.compile(r"(!?\[[^\]]*\]\()([^)]*)(\))")
    candidates = [ROOT / "README.md", ROOT / "PROJECT_HANDOFF.md"]
    for directory in ("docs", "reports", "deliverables"):
        candidates.extend((ROOT / directory).rglob("*.md"))
    for doc in candidates:
        if not doc.is_file():
            continue
        new_source = doc.relative_to(ROOT)
        old_source = next((old for old, new in moves.items() if new == new_source), new_source)
        original = doc.read_text(encoding="utf-8")

        def update(match: re.Match) -> str:
            destination = match.group(2)
            if not destination or destination.startswith(("#", "mailto:", "http:", "https:")):
                return match.group(0)
            path_part, separator, anchor = destination.partition("#")
            if not path_part:
                return match.group(0)
            old_target = Path(os.path.normpath(str(old_source.parent / unquote(path_part).strip("<>"))))
            new_target = relocate(old_target)
            new_relative = os.path.relpath(ROOT / new_target, (ROOT / new_source).parent)
            rewritten = new_relative + (separator + anchor if separator else "")
            return match.group(1) + rewritten + match.group(3)

        revised = link.sub(update, original)
        if revised != original:
            if new_source in {Path("docs/FINALIZATION_P2_INTEGRATION_PROTOCOL.md"), Path("docs/PHASE4_STATISTICAL_ANALYSIS_PLAN.md")}:
                raise ValueError(f"Protected protocol would change: {doc}")
            doc.write_text(revised, encoding="utf-8")
    print(f"Moved {len(moves)} Markdown files; rebased relative links")


if __name__ == "__main__":
    main()
