"""Seed company and persona data from markdown sources into structured JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .loaders import load_seed_sources
from .models import SeedBundle
from .prompts import build_all_prompts


def default_paths(base_dir: Path | None = None) -> tuple[Path, Path]:
    root = base_dir or Path(__file__).resolve().parents[2]
    test_data = root / "test_data"
    output = root / "data" / "seeded"
    return test_data, output


def seed(
    test_data_dir: Path | None = None,
    output_dir: Path | None = None,
    *,
    meeting_topic: str | None = None,
) -> SeedBundle:
    """Load markdown sources, build prompts, and write JSON artifacts."""
    default_test_data, default_output = default_paths()
    test_data = test_data_dir or default_test_data
    output = output_dir or default_output

    company, personas = load_seed_sources(test_data)
    prompts = build_all_prompts(company, personas, meeting_topic=meeting_topic)
    bundle = SeedBundle(company=company, personas=personas, prompts=prompts)

    output.mkdir(parents=True, exist_ok=True)
    (output / "company_profile.json").write_text(
        company.model_dump_json(indent=2),
        encoding="utf-8",
    )

    personas_dir = output / "personas"
    personas_dir.mkdir(exist_ok=True)
    for role_key, persona in personas.items():
        (personas_dir / f"{role_key.lower()}.json").write_text(
            persona.model_dump_json(indent=2),
            encoding="utf-8",
        )

    prompts_dir = output / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    for role_key, prompt in prompts.items():
        payload = prompt.model_dump(mode="json")
        (prompts_dir / f"{role_key.lower()}_system_prompt.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (prompts_dir / f"{role_key.lower()}_system_prompt.txt").write_text(
            prompt.system_prompt,
            encoding="utf-8",
        )

    (output / "seed_bundle.json").write_text(
        json.dumps(
            {
                "company": company.model_dump(mode="json"),
                "personas": {k: v.model_dump(mode="json") for k, v in personas.items()},
                "prompt_roles": list(prompts.keys()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return bundle
