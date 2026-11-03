import hashlib
import json

import pytest

from ai_research_trends.web.restore_artifacts import restore_package, sha256, verify_package


def package(tmp_path, kind="web"):
    root = tmp_path / "source"
    root.mkdir()
    path = root / "nested" / "item.txt"
    path.parent.mkdir()
    path.write_text("verified local data", encoding="utf-8")
    inventory = {"nested/item.txt": {"sha256": sha256(path), "bytes": path.stat().st_size}}
    manifest = {"status": "complete", "complete": True, "outputs" if kind == "web" else "files": inventory}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_restore_verified_copy_dry_run_and_refuse_overwrite(tmp_path):
    source = package(tmp_path)
    dest = tmp_path / "new" / "package"
    preview = restore_package(source, dest, "web")
    assert preview["files"] == 1 and not preview["copied"]
    assert not dest.exists()
    copied = restore_package(source, dest, "web", execute=True)
    assert copied["copied"] and copied["manifest_sha256"] == sha256(dest / "manifest.json")
    assert verify_package(dest, "web")[0] == verify_package(source, "web")[0]
    with pytest.raises(ValueError, match="already exists"):
        restore_package(source, dest, "web", execute=True)


def test_restore_rejects_corrupt_source_and_unsafe_manifest(tmp_path):
    source = package(tmp_path, "model")
    (source / "nested" / "item.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        restore_package(source, tmp_path / "dest", "model", execute=True)
    assert not (tmp_path / "dest").exists()
    manifest = json.loads((source / "manifest.json").read_text())
    manifest["files"] = {"../secret": {"sha256": hashlib.sha256(b"").hexdigest(), "bytes": 0}}
    (source / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Unsafe"):
        verify_package(source, "model")


def test_restore_refuses_incomplete_manifest(tmp_path):
    source = package(tmp_path)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["complete"] = False
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="not complete"):
        verify_package(source, "web")
