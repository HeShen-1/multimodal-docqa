from __future__ import annotations

from pathlib import Path


DOCQA_WORKSPACE_DIRS = (
    "public_raw",
    "public_norm",
    "local_raw_docs",
    "local_norm_docs",
    "annotations",
    "prepared",
    "eval",
)


def ensure_docqa_workspace(base_dir: Path | str) -> dict[str, Path]:
    workspace_root = Path(base_dir)
    workspace_root.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    for directory_name in DOCQA_WORKSPACE_DIRS:
        directory_path = workspace_root / directory_name
        directory_path.mkdir(parents=True, exist_ok=True)
        paths[directory_name] = directory_path

    return paths


def default_workspace_root() -> Path:
    return Path("scripts/training/data/docqa_workspace")
