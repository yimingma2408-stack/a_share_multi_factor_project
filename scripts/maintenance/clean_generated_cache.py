"""Safely remove only temporary, ignored formal-EOT parallel shards."""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = next(parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").is_file())
TARGETS = (
    ROOT / "data/processed/eot_factor_lifecycle_test",
    ROOT / "reports/eot_factor_lifecycle_test",
)


def candidates() -> list[Path]:
    files: list[Path] = []
    for directory in TARGETS:
        files.extend(sorted(directory.glob("shard_*_panel.parquet")))
        files.extend(sorted(directory.glob("shard_*_coordinates.parquet")))
        files.extend(sorted(directory.glob("shard_*_computation.csv")))
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Actually remove the listed temporary shard files.")
    args = parser.parse_args()
    files = candidates()
    if not files:
        print("No temporary formal-EOT shard files found.")
        return
    if not args.confirm:
        print("Dry run; pass --confirm to remove only these temporary files:")
        print("\n".join(str(path.relative_to(ROOT)) for path in files))
        return
    for path in files:
        path.unlink()
    print(f"Removed {len(files)} temporary formal-EOT shard files.")


if __name__ == "__main__":
    main()
