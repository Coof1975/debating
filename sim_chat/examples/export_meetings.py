#!/usr/bin/env python3
"""Export meeting JSON records under data/meetings/ to readable .txt files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sim_chat.export import export_all_meetings, export_meeting_record  # noqa: E402
from sim_chat.persistence import default_storage_dir  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "meeting_id",
        nargs="?",
        help="Export a single meeting by ID (omit to export all JSON files)",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help=f"Directory containing meeting JSON (default: {default_storage_dir()})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for .txt output (default: same as input-dir)",
    )
    args = parser.parse_args()

    storage = args.input_dir or default_storage_dir()
    output = args.output_dir or storage

    if args.meeting_id:
        path = export_meeting_record(args.meeting_id, storage_dir=storage, output_dir=output)
        print(f"Exported: {path}")
        return

    paths = export_all_meetings(storage_dir=storage, output_dir=output)
    if not paths:
        print(f"No meeting JSON files found in {storage}")
        return

    print(f"Exported {len(paths)} file(s) to {output}:")
    for path in paths:
        print(f"  - {path.name}")


if __name__ == "__main__":
    main()
