"""Standard information-retrieval and matching metrics.

Ranking (discovery), with graded relevance 0-3 per result:
- Precision@k: share of the top k that are relevant (grade >= threshold).
- Recall@k:    share of all known relevant results that appear in the top k.
- nDCG@k:      discounted cumulative gain with graded gains (2^grade - 1), normalised by the
               ideal ordering of every judged result (Järvelin & Kekäläinen, 2002).
- MRR:         1 / rank of the first relevant result.
- AP:          average precision over relevant results (mean over queries gives MAP).

Matching (price comparison), with binary same-product labels:
- precision, recall and F1 over the offers shown versus all offers judged to be matches.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass


def precision_at_k(grades: Sequence[int], k: int, threshold: int = 2) -> float:
    top = grades[:k]
    return sum(g >= threshold for g in top) / k if k else 0.0


def recall_at_k(grades: Sequence[int], total_relevant: int, k: int, threshold: int = 2) -> float:
    if total_relevant == 0:
        return 0.0
    return sum(g >= threshold for g in grades[:k]) / total_relevant


def dcg(grades: Sequence[int]) -> float:
    return sum((2**g - 1) / math.log2(rank + 1) for rank, g in enumerate(grades, start=1))


def ndcg_at_k(grades: Sequence[int], k: int, ideal_pool: Sequence[int] | None = None) -> float:
    """nDCG@k. `ideal_pool` holds every judged grade for the query (defaults to `grades`)."""
    ideal = dcg(sorted(ideal_pool if ideal_pool is not None else grades, reverse=True)[:k])
    return dcg(grades[:k]) / ideal if ideal else 0.0


def reciprocal_rank(grades: Sequence[int], threshold: int = 2) -> float:
    return next((1 / rank for rank, g in enumerate(grades, start=1) if g >= threshold), 0.0)


def average_precision(grades: Sequence[int], total_relevant: int, threshold: int = 2) -> float:
    if total_relevant == 0:
        return 0.0
    hits, total = 0, 0.0
    for rank, grade in enumerate(grades, start=1):
        if grade >= threshold:
            hits += 1
            total += hits / rank
    return total / total_relevant


@dataclass(frozen=True)
class MatchScores:
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int


def match_scores(shown: set[str], matches: set[str], judged: set[str]) -> MatchScores:
    """Precision/recall/F1 of shown offers. Unjudged shown offers are excluded from precision."""
    shown_judged = shown & judged
    tp = len(shown_judged & matches)
    fp = len(shown_judged - matches)
    fn = len(matches - shown)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return MatchScores(precision, recall, f1, tp, fp, fn)
