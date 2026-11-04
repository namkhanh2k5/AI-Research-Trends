"""Resolve recorded research inputs inside the current repository checkout.

Older immutable manifests may contain absolute paths from the machine that
created them. Remapping changes only where bytes are read; callers must still
verify each manifest's recorded SHA-256 before using an input.
"""

from __future__ import annotations

from pathlib import Path


_PROJECT_ROOTS = frozenset({"data", "config", "docs", "models"})


def repository_root(run_dir: Path) -> Path:
    """Find the checkout owning a versioned run, never a different local clone."""
    directory = run_dir.resolve()
    for candidate in (directory, *directory.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise ValueError(f"Run is not inside a project checkout: {run_dir}")


def resolve_manifest_input(recorded_path: str, run_dir: Path) -> Path:
    """Map a project input from a manifest to the current checkout safely.

    Only the project's known top-level artifact directories are accepted.
    Ambiguous absolute paths, traversal and symlinks escaping the checkout are
    rejected rather than reading arbitrary files from another machine.
    """
    if not isinstance(recorded_path, str) or not recorded_path:
        raise ValueError("Manifest input path is empty")
    recorded = Path(recorded_path.replace("\\", "/"))
    if ".." in recorded.parts:
        raise ValueError(f"Manifest input path traverses outside project: {recorded_path}")
    if recorded.is_absolute():
        anchors = [i for i, part in enumerate(recorded.parts) if part in _PROJECT_ROOTS]
        if len(anchors) != 1:
            raise ValueError(f"Ambiguous manifest input path: {recorded_path}")
        relative = Path(*recorded.parts[anchors[0]:])
    else:
        relative = recorded
    if not relative.parts or relative.parts[0] not in _PROJECT_ROOTS:
        raise ValueError(f"Manifest input is not a project artifact: {recorded_path}")
    root = repository_root(run_dir)
    candidate = root / relative
    if not candidate.resolve().is_relative_to(root):
        raise ValueError(f"Manifest input escapes project checkout: {recorded_path}")
    return candidate
