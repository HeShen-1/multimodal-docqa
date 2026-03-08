from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.training.docqa_workspace import default_workspace_root
from scripts.training.prepare_local_corpus import generate_seed_annotations


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate blank annotation templates from normalized local docs.")
    parser.add_argument("--workspace-root", default=str(default_workspace_root()))
    parser.add_argument("--answerable-limit-per-doc", type=int, default=3)
    args = parser.parse_args()

    summary = generate_seed_annotations(
        Path(args.workspace_root),
        answerable_limit_per_doc=args.answerable_limit_per_doc,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
