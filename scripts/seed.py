#!/usr/bin/env python3
"""CLI entry point to seed persona and company data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from debating.seed import seed  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed company profile and meeting personas from test_data markdown files.",
    )
    parser.add_argument(
        "--test-data",
        type=Path,
        default=ROOT / "test_data",
        help="Directory containing COMPANY_profile.md and *_persona.md files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "seeded",
        help="Directory to write seeded JSON and prompt files",
    )
    parser.add_argument(
        "--topic",
        default=None,
        help="Optional meeting topic for sample prompt previews (stored prompts are topic-agnostic)",
    )
    args = parser.parse_args()

    bundle = seed(args.test_data, args.output, meeting_topic=args.topic)

    print(f"Seeded company: {bundle.company.company_name} ({bundle.company.report_period})")
    print(f"Personas: {', '.join(bundle.personas.keys())}")
    print(f"Output: {args.output.resolve()}")
    for role_key in bundle.prompts:
        txt_path = args.output / "prompts" / f"{role_key.lower()}_system_prompt.txt"
        print(f"  - {role_key}: {txt_path}")


if __name__ == "__main__":
    main()
