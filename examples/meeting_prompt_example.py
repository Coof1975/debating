#!/usr/bin/env python3
"""Example: load seeded prompts and prepare LLM chat messages for a meeting turn."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from debating import PersonaRole, build_chat_messages, load_seed_sources, seed  # noqa: E402
from debating.prompts import build_persona_prompt  # noqa: E402


def main() -> None:
    test_data = ROOT / "test_data"
    output = ROOT / "data" / "seeded"

    if not (output / "seed_bundle.json").exists():
        seed(test_data, output)

    company, personas = load_seed_sources(test_data)
    ceo_prompt = build_persona_prompt(personas["CEO"], company, personas)

    opening = (
        "Cuộc họp bắt đầu. CEO mở đầu: chúng ta cần thống nhất kế hoạch "
        "thúc đẩy bán hàng Keos trong tháng tới. Mỗi người nêu quan điểm."
    )
    messages = build_chat_messages(ceo_prompt, opening)

    print("=== Sample OpenAI-style messages for CEO ===")
    print(json.dumps(messages, ensure_ascii=False, indent=2)[:1200], "...\n")

    print("Available roles:", ", ".join(r.value for r in PersonaRole))


if __name__ == "__main__":
    main()
