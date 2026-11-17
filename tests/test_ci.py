import json
from pathlib import Path

import pytest

from scripts.check_repository import check_files
from scripts.prepare_ci_context import COPY_FILES, prepare_context


def test_ci_context_excludes_models_and_preserves_source(tmp_path):
    root = Path(__file__).resolve().parents[1]
    context = prepare_context(tmp_path / "context")
    names = {path.relative_to(context).as_posix() for path in context.rglob("*") if path.is_file()}
    assert set(COPY_FILES) <= names
    assert not any(name.endswith((".joblib", ".ubj", ".db", ".csv", ".zip")) for name in names)
    assert not any(name.startswith("data/processed/") for name in names)
    assert (context / "Dockerfile").read_bytes() == (root / "Dockerfile").read_bytes()
    assert {path.name for path in (context / "artifacts").iterdir()} == {"ci_context.json"}
    marker = json.loads((context / "artifacts/ci_context.json").read_text())
    assert marker["expected_model_ready"] is False and marker["deployable_model_bundle"] is False
    with pytest.raises(ValueError, match="never overwritten"):
        prepare_context(context)
    assert (context / "Dockerfile").read_bytes() == (root / "Dockerfile").read_bytes()


def test_repository_guard_blocks_private_files_and_detects_credentials(tmp_path):
    (tmp_path / "safe.py").write_text("print('hello')\n")
    (tmp_path / ".env.example").write_text("SENTINEL_API_TARGET=http://127.0.0.1:8001\n")
    (tmp_path / "leak.txt").write_text("ghp_" + "a" * 36)
    assert check_files(["safe.py", ".env.example"], tmp_path) == []
    blocked = ["artifacts/model.ubj", "data/processed/train.csv", ".env.local", "frontend/node_modules/x.js", "local.db-wal", "leak.txt"]
    assert len(check_files(blocked, tmp_path)) == len(blocked)
