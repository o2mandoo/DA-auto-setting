"""Small retrieval-quality metrics for semantic-gold benchmark cases.

These helpers are intentionally deterministic and local.  They do not call a
backend directly; callers pass already observed ranked result ids so benchmark
reports can explain whether a semantic case was merely found somewhere or was
ranked high enough to be useful.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable


@dataclass(frozen=True)
class RetrievalMetrics:
    expected_count: int
    retrieved_count: int
    hit_count: int
    recall_at_k: float
    mrr: float
    first_hit_rank: int | None
    missing_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def compute_retrieval_metrics(
    ranked_ids: Iterable[str],
    expected_ids: Iterable[str],
    *,
    k: int = 10,
) -> RetrievalMetrics:
    """Compute recall@k and MRR for a single semantic-gold retrieval case."""

    ranked = [str(value) for value in ranked_ids if str(value).strip()][: max(0, int(k))]
    expected = tuple(dict.fromkeys(str(value) for value in expected_ids if str(value).strip()))
    if not expected:
        return RetrievalMetrics(
            expected_count=0,
            retrieved_count=len(ranked),
            hit_count=0,
            recall_at_k=1.0,
            mrr=0.0,
            first_hit_rank=None,
            missing_ids=(),
        )

    expected_set = set(expected)
    hits = [value for value in ranked if value in expected_set]
    first_hit_rank = next((index + 1 for index, value in enumerate(ranked) if value in expected_set), None)
    missing = tuple(value for value in expected if value not in set(ranked))
    return RetrievalMetrics(
        expected_count=len(expected),
        retrieved_count=len(ranked),
        hit_count=len(set(hits)),
        recall_at_k=round(len(set(hits)) / len(expected_set), 6),
        mrr=round((1.0 / first_hit_rank) if first_hit_rank else 0.0, 6),
        first_hit_rank=first_hit_rank,
        missing_ids=missing,
    )


__all__ = ["RetrievalMetrics", "compute_retrieval_metrics"]
