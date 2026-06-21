#!/usr/bin/env python3
"""Test Marketing persona response via Gemini 2.5 Flash.

Scenario: Product director pushes back on rapid brand/package change requests
from Marketing; Marketing must reply in character during the Keos meeting.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from debating import load_seed_sources, seed  # noqa: E402
from debating.prompts import build_persona_prompt  # noqa: E402

MODEL = "gemini-2.5-flash"

PRODUCT_MESSAGE = """\
[Cuộc họp: Kế hoạch thúc đẩy bán hàng Keos — Q2/2026]

Trần Minh Tuấn (Giám đốc Sản xuất) vừa phát biểu:

"Chị Hương, em nói thẳng. Tuần trước Marketing đòi đổi layout bao bì Keos 500g sang tone pastel cho campaign TikTok, tuần này lại muốn thêm SKU 1.2kg kèm quà tặng sample — nhà máy không chạy kiểu đổi khuôn liên tục như thế được.

Dây chuyền Keos mới vận hành ở mức tối đa 200 tấn/tháng, công nhân chưa quen quy trình kiểm soát độ ẩm. Mỗi lần đổi quy cách đóng gói là setup lại 2–3 ngày, hao hụt nguyên liệu tăng, tỷ lệ lỗi phình ra. Bao bì chống ẩm đặc chủng còn đang kẹt ở cảng Cát Lái chậm thêm 2 tuần — giờ đòi đổi thiết kế nữa thì em chịu sao nổi?

Em chỉ muốn chạy một lệnh sản xuất lớn, ổn định, đảm bảo chất lượng hạt mềm cao cấp. Nếu Marketing cứ đòi bắt trend nhanh như vậy thì năng lực nhà máy không theo kịp — và nguy cơ hàng lỗi, công nhân tăng ca kiệt sức là em không chấp nhận."

Hãy phản hồi với tư cách Trần Thu Hương (Marketing). Trả lời trực tiếp anh Tuấn trong cuộc họp.
"""


def load_api_key() -> str:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        env_path = ROOT / ".env"
        hint = (
            f"Save GOOGLE_API_KEY to {env_path} (see .env.example). "
            "The file exists but appears empty on disk."
            if env_path.exists() and env_path.stat().st_size == 0
            else f"Set GOOGLE_API_KEY in {env_path} (see .env.example)."
        )
        raise SystemExit(f"Missing GOOGLE_API_KEY (or GEMINI_API_KEY). {hint}")
    return api_key


def ensure_seeded() -> None:
    output = ROOT / "data" / "seeded"
    if not (output / "seed_bundle.json").exists():
        seed(ROOT / "test_data", output)


def call_gemini(system_prompt: str, user_message: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=load_api_key())
    response = client.models.generate_content(
        model=MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.9,
            max_output_tokens=1024,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return (response.text or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prompts only; do not call Gemini API",
    )
    args = parser.parse_args()

    ensure_seeded()
    company, personas = load_seed_sources(ROOT / "test_data")
    marketing_prompt = build_persona_prompt(personas["MARKETING"], company, personas)

    print("=" * 72)
    print("SCENARIO: Product → Marketing (factory capacity vs brand/package pace)")
    print("=" * 72)
    print("\n--- Product message ---\n")
    print(PRODUCT_MESSAGE.strip())

    if args.dry_run:
        print("\n--- Dry run: Marketing system prompt (first 1500 chars) ---\n")
        print(marketing_prompt.system_prompt[:1500], "...")
        return

    print("\n--- Calling Gemini ---\n")
    print(f"Model: {MODEL}")
    print(f"Persona: {marketing_prompt.name} ({marketing_prompt.role.value})\n")

    try:
        reply = call_gemini(marketing_prompt.system_prompt, PRODUCT_MESSAGE)
    except Exception as exc:
        raise SystemExit(f"Gemini API call failed: {exc}") from exc

    print("--- Marketing response ---\n")
    print(reply)
    print()


if __name__ == "__main__":
    main()
