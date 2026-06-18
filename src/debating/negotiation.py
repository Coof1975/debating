"""Negotiation / compromise parameters for meeting personas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NegotiationProfile(BaseModel):
    """How willing a persona is to compromise while protecting department interests."""

    compromise_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    min_interest_retention: float = Field(default=0.7, ge=0.0, le=1.0)
    director_sensitivity: float = Field(default=0.6, ge=0.0, le=1.0)
    deadlock_tolerance: float = Field(default=0.3, ge=0.0, le=1.0)


DEFAULT_NEGOTIATION_BY_ROLE: dict[str, NegotiationProfile] = {
    "CFO": NegotiationProfile(
        compromise_threshold=0.25,
        min_interest_retention=0.85,
        director_sensitivity=0.45,
        deadlock_tolerance=0.2,
    ),
    "PRODUCT": NegotiationProfile(
        compromise_threshold=0.35,
        min_interest_retention=0.75,
        director_sensitivity=0.5,
        deadlock_tolerance=0.25,
    ),
    "MARKETING": NegotiationProfile(
        compromise_threshold=0.55,
        min_interest_retention=0.65,
        director_sensitivity=0.65,
        deadlock_tolerance=0.4,
    ),
    "SALE": NegotiationProfile(
        compromise_threshold=0.65,
        min_interest_retention=0.6,
        director_sensitivity=0.7,
        deadlock_tolerance=0.45,
    ),
    "CEO": NegotiationProfile(
        compromise_threshold=0.70,
        min_interest_retention=0.55,
        director_sensitivity=0.85,
        deadlock_tolerance=0.35,
    ),
}


def _role_key(role: str | Any) -> str:
    value = getattr(role, "value", role)
    return str(value).upper()


def default_negotiation_for_role(role: str) -> NegotiationProfile:
    role_key = _role_key(role)
    return DEFAULT_NEGOTIATION_BY_ROLE.get(role_key, NegotiationProfile()).model_copy()


def negotiation_from_metadata(
    metadata: dict[str, Any] | None,
    *,
    role: str,
) -> NegotiationProfile:
    """Resolve negotiation profile from persona metadata with role defaults."""
    if metadata:
        raw = metadata.get("negotiation")
        if isinstance(raw, dict) and raw:
            try:
                return NegotiationProfile.model_validate(raw)
            except Exception:
                pass
    return default_negotiation_for_role(role)


def format_negotiation_prompt_block(profile: NegotiationProfile) -> str:
    retention_pct = int(round(profile.min_interest_retention * 100))
    return f"""\
# HỒ SƠ ĐÀM PHÁN
- Chỉ số thỏa hiệp: {profile.compromise_threshold:.2f}/1.0 (0 = cực cứng, 1 = dễ nhượng)
- Tối thiểu giữ lợi ích bộ phận: {retention_pct}%
- Nhạy cảm áp lực từ Sếp (CEO): {profile.director_sensitivity:.2f}/1.0
- Chịu đựng bế tắc họp: {profile.deadlock_tolerance:.2f}/1.0

Mục tiêu tối thượng: cuộc họp phải ra kết quả cho Sếp (CEO).
Nếu anh cố chấp gây bế tắc vô nghĩa, Sếp sẽ đánh giá anh kém năng lực điều phối.
Khi chỉ số thỏa hiệp thấp: vẫn phải "Yes, and..." — không phủ nhận sạch trơn luận điểm đối phương.
"""


def effective_compromise_threshold(
    profile: NegotiationProfile,
    *,
    stagnation_score: int = 0,
    enable_dynamic: bool = False,
) -> float:
    """Optionally soften stance when debate stagnates (director pressure)."""
    base = profile.compromise_threshold
    if not enable_dynamic or stagnation_score <= 0:
        return base
    factor = min(1.0, stagnation_score * 0.12)
    boosted = base * (1.0 + profile.director_sensitivity * factor)
    return min(1.0, boosted)
