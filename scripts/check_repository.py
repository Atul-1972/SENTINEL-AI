"""Check the Git file list without printing secret values or reading ignored files."""

import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 5 * 1024 * 1024
PRIVATE_DIRECTORIES = {
    ".git", ".aws", ".codex", ".agents", ".venv", ".venv-model", ".python",
    "venv", "node_modules", "__pycache__", "artifacts", "mlruns", "mlartifacts",
    ".ci-context", ".ci-output", "test-results", "playwright-report", ".sites-runtime",
}
PRIVATE_EXTENSIONS = {".joblib", ".ubj", ".pkl", ".zip", ".pem", ".key", ".db"}
SECRET_PATTERN = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    rb"|\bgh[pousr]_[A-Za-z0-9]{30,}\b"
    rb"|\bgithub_pat_[A-Za-z0-9_]{30,}\b"
    rb"|\bAKIA[A-Z0-9]{16}\b"
)


def check_files(names, root=ROOT):
    errors = []
    for name in names:
        relative = PurePosixPath(name)
        path = root / name
        if (
            relative.is_absolute() or ".." in relative.parts
            or any(part in PRIVATE_DIRECTORIES for part in relative.parts)
            or relative.parts[:2] in {("data", "raw"), ("data", "processed"), ("frontend", "dist")}
            or relative.suffix.lower() in PRIVATE_EXTENSIONS
            or ".db-" in relative.name
            or (relative.name.startswith(".env") and relative.name != ".env.example")
        ):
            errors.append(f"{name}: local/generated/private file must not be tracked")
            continue
        if path.is_symlink():
            errors.append(f"{name}: review the symlink before committing")
        elif not path.is_file():
            errors.append(f"{name}: tracked file is missing")
        elif path.stat().st_size > MAX_BYTES:
            errors.append(f"{name}: exceeds the 5 MB source-file limit")
        elif SECRET_PATTERN.search(path.read_bytes()):
            errors.append(f"{name}: potential credential; remove it before committing")
    return errors


def main():
    names = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT,
    ).decode("utf-8").rstrip("\0").split("\0")
    names = [name for name in names if name]
    if not names:
        raise SystemExit("No tracked files. Stage the intended source files before this check.")
    errors = check_files(names)
    if errors:
        raise SystemExit("Repository check failed:\n" + "\n".join(errors))
    print(f"Repository check passed: {len(names)} source/report/example files; no excluded files detected.")


if __name__ == "__main__":
    main()
