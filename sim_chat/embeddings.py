"""Lightweight text embeddings for stagnation detection (no external API)."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .config import MeetingConfig
from .models import DialogueTurn


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[\wÀ-ỹ]+", text.lower())
    return [token for token in tokens if len(token) > 1]


def _vectorize(text: str) -> Counter[str]:
    return Counter(_tokenize(text))


def cosine_similarity(left: str, right: str) -> float:
    """Bag-of-words cosine similarity in [0, 1]."""
    if not left.strip() or not right.strip():
        return 0.0
    left_vec = _vectorize(left)
    right_vec = _vectorize(right)
    if not left_vec or not right_vec:
        return 0.0

    shared = set(left_vec) & set(right_vec)
    dot = sum(left_vec[token] * right_vec[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left_vec.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vec.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def recent_turn_similarity(messages: list[DialogueTurn], window: int = 4) -> float:
    """Average pairwise similarity among consecutive turns in the recent window."""
    if len(messages) < 2:
        return 0.0
    recent = messages[-window:]
    contents = [turn.content for turn in recent]
    if len(contents) < 2:
        return 0.0

    scores: list[float] = []
    for index in range(len(contents) - 1):
        scores.append(cosine_similarity(contents[index], contents[index + 1]))
    return sum(scores) / len(scores) if scores else 0.0


def novel_token_ratio(latest: str, prior_contents: list[str]) -> float:
    """Share of tokens in `latest` that did not appear in prior turns."""
    latest_tokens = set(_tokenize(latest))
    if not latest_tokens:
        return 0.0
    prior_tokens: set[str] = set()
    for content in prior_contents:
        prior_tokens.update(_tokenize(content))
    novel = latest_tokens - prior_tokens
    return len(novel) / len(latest_tokens)


def max_similarity_to_recent(latest: str, prior_contents: list[str]) -> float:
    """Highest cosine similarity between `latest` and any prior turn."""
    if not prior_contents:
        return 0.0
    return max(cosine_similarity(latest, content) for content in prior_contents)


_CLAIM_PATTERN = re.compile(
    r"\d+[\.,]?\d*\s*%?"
    r"|chiết\s*khấu|ngân\s*sách|roadmap|deadline|quý\s*\d|Q\d"
    r"|CRM|ERP|Keos|đại\s*lý|doanh\s*thu|lợi\s*nhuận|margin",
    re.IGNORECASE,
)


def substantive_claims(text: str) -> set[str]:
    """Extract numbers and recurring debate keywords for overlap checks."""
    return {match.group(0).lower().replace(" ", "") for match in _CLAIM_PATTERN.finditer(text)}


def claim_overlap_ratio(latest: str, prior_contents: list[str]) -> float:
    """Share of substantive claims in the latest turn already seen recently."""
    latest_claims = substantive_claims(latest)
    if not latest_claims:
        return 0.0
    prior_claims: set[str] = set()
    for content in prior_contents:
        prior_claims.update(substantive_claims(content))
    if not prior_claims:
        return 0.0
    repeated = latest_claims & prior_claims
    return len(repeated) / len(latest_claims)


@dataclass(frozen=True)
class StagnationSignals:
    consecutive_similarity: float
    max_similarity: float
    novel_ratio: float
    claim_overlap: float
    is_stagnant: bool


def compute_stagnation_signals(
    messages: list[DialogueTurn],
    config: MeetingConfig,
) -> StagnationSignals:
    """Multi-signal view of whether the latest turn adds new substance."""
    window = max(2, config.stagnation_window)
    recent = messages[-window:]
    if len(recent) < 2:
        return StagnationSignals(0.0, 0.0, 1.0, 0.0, False)

    latest = recent[-1].content
    prior_contents = [turn.content for turn in recent[:-1]]
    consecutive = recent_turn_similarity(messages, window=min(4, len(recent)))
    max_sim = max_similarity_to_recent(latest, prior_contents)
    novel_ratio = novel_token_ratio(latest, prior_contents)
    claim_overlap = claim_overlap_ratio(latest, prior_contents)

    repetitive_claims = (
        claim_overlap >= 0.6
        and max_sim >= config.stagnation_max_similarity_threshold - 0.05
        and novel_ratio <= config.stagnation_min_novel_token_ratio + 0.08
    )
    low_novelty = (
        max_sim >= config.stagnation_max_similarity_threshold
        and novel_ratio <= config.stagnation_min_novel_token_ratio
    )
    consecutive_loop = consecutive >= config.stagnation_similarity_threshold
    is_stagnant = low_novelty or consecutive_loop or repetitive_claims

    return StagnationSignals(
        consecutive_similarity=consecutive,
        max_similarity=max_sim,
        novel_ratio=novel_ratio,
        claim_overlap=claim_overlap,
        is_stagnant=is_stagnant,
    )
