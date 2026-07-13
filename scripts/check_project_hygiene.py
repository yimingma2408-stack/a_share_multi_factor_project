"""Read-only checks for repository layout and generated-artifact boundaries."""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOT_FILES = {
    ".gitignore",
    "ARTIFACT_POLICY.md",
    "README.md",
    "environment.yml",
    "pyproject.toml",
    "requirements-lock.txt",
    "requirements.txt",
    "FORMAL_EOT_RESEARCH_SPEC.md",
    "RESEARCH_PROJECT_OUTLINE.md",
}
ALLOWED_ROOT_DIRS = {
    ".git",
    ".vscode",
    "build",
    "config",
    "data",
    "dist",
    "notebook",
    "reports",
    "results",
    "scripts",
    "src",
    "tests",
}


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return [line for line in result.stdout.splitlines() if line]


def readme_paths() -> set[str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    candidates = re.findall(r"`([^`\n]+)`", text)
    return {
        candidate.rstrip("/.,;:")
        for candidate in candidates
        if "/" in candidate or Path(candidate).suffix in {".md", ".yaml", ".py"}
    }


def checks() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    tracked = tracked_files()

    committed_junk = [
        path
        for path in tracked
        if (ROOT / path).exists()
        and (
            "/__pycache__/" in f"/{path}"
            or path.endswith((".pyc", ".pyo", ".DS_Store"))
            or ".egg-info/" in path
        )
    ]
    if committed_junk:
        errors.append("Committed cache/system files: " + ", ".join(committed_junk))

    root_clutter = sorted(
        item.name
        for item in ROOT.iterdir()
        if (item.is_file() and item.name not in ALLOWED_ROOT_FILES)
        or (item.is_dir() and item.name not in ALLOWED_ROOT_DIRS and not item.name.startswith("."))
    )
    if root_clutter:
        warnings.append("Unexpected root entries: " + ", ".join(root_clutter))

    for directory in (ROOT / "data/raw", ROOT / "data/processed"):
        if directory.exists() and not (directory / ".gitkeep").exists():
            warnings.append(f"Missing keep-file: {directory.relative_to(ROOT)}/.gitkeep")

    broken = sorted(path for path in readme_paths() if not (ROOT / path).exists())
    if broken:
        warnings.append("README references missing paths: " + ", ".join(broken))

    shards = sorted(
        list((ROOT / "data/processed/eot_factor_lifecycle_test").glob("shard_*"))
        + list((ROOT / "reports/eot_factor_lifecycle_test").glob("shard_*"))
    )
    if shards:
        warnings.append(f"Temporary formal-EOT shards present: {len(shards)}")
    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args()
    errors, warnings = checks()
    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARNING: {message}")
    if errors or (args.strict and warnings):
        raise SystemExit(1)
    print("PROJECT_HYGIENE_OK")


if __name__ == "__main__":
    main()
