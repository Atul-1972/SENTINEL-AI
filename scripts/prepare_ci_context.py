"""Prepare an isolated, artifact-free context for the normal inference Dockerfile.

CI checks image packaging and honest missing-model behavior. It never fabricates
a trained model or quality gate, and never changes the user's artifacts folder.
"""

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPY_FILES = (
    "Dockerfile", ".dockerignore", "requirements-model.txt",
    "backend/requirements-api.txt",
    "reports/inference_smoke_test.json", "reports/model_comparison.json",
    "data/sample/api_request.json", "data/sample/api_batch_request.json",
)


def prepare_context(destination, root=ROOT):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Choose a new context directory; existing paths are never overwritten.")
    sources = [root / name for name in COPY_FILES] + sorted((root / "backend").glob("*.py"))
    for source in sources:
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"Expected a regular source file: {source.name}")
    destination.mkdir(parents=True)
    for source in sources:
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    artifacts = destination / "artifacts"
    artifacts.mkdir()
    (artifacts / "ci_context.json").write_text(json.dumps({
        "purpose": "CI packaging check only; intentionally contains no trained models.",
        "expected_model_ready": False,
        "deployable_model_bundle": False,
    }, indent=2) + "\n", encoding="utf-8")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(f"Artifact-free CI context: {prepare_context(args.destination)}")


if __name__ == "__main__":
    main()
