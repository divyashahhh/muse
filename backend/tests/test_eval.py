import math

import pytest

from app.eval.metrics import (
    average_precision,
    match_scores,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.eval.report import ShownListing, evaluate


def test_ranking_metrics_on_a_known_ordering() -> None:
    grades = [3, 0, 2, 1, 0]
    assert precision_at_k(grades, 5) == pytest.approx(0.4)
    assert recall_at_k(grades, total_relevant=4, k=5) == pytest.approx(0.5)
    assert reciprocal_rank([0, 1, 2]) == pytest.approx(1 / 3)
    assert average_precision(grades, total_relevant=2) == pytest.approx((1 + 2 / 3) / 2)
    ideal = 7 + 3 / math.log2(3) + 1 / 2
    actual = 7 + 3 / 2 + 1 / math.log2(5)
    assert ndcg_at_k(grades, 5) == pytest.approx(actual / ideal)
    assert ndcg_at_k([3, 2, 1], 3) == pytest.approx(1.0)


def test_match_scores_ignore_unjudged_offers_in_precision() -> None:
    scores = match_scores(shown={"a", "b", "x"}, matches={"a", "c"}, judged={"a", "b", "c"})
    assert (scores.true_positives, scores.false_positives, scores.false_negatives) == (1, 1, 1)
    assert scores.precision == scores.recall == scores.f1 == pytest.approx(0.5)


def test_evaluate_report() -> None:
    judgements = [
        {
            "item_id": "i1",
            "kind": "discover",
            "url": "https://s.example/a?utm_source=x",
            "grade": 3,
        },
        {"item_id": "i1", "kind": "discover", "url": "https://s.example/b", "grade": 0},
        {"item_id": "i1", "kind": "discover", "url": "https://s.example/unshown", "grade": 2},
        {"item_id": "i1", "kind": "offer", "url": "https://shop.example/p", "match": True},
        {"item_id": "i1", "kind": "offer", "url": "https://fake.example/p", "match": False},
    ]
    shown = [
        ShownListing("i1", "discover", "https://s.example/b", 1),
        ShownListing("i1", "discover", "https://s.example/a", 0),
        ShownListing("i1", "offer", "https://shop.example/p", 0),
        ShownListing("i1", "offer", "https://fake.example/p", 1),
    ]
    report = evaluate(judgements, shown)
    assert report["items_judged"] == {"discover": 1, "offer": 1}
    assert report["ranking"]["MRR"] == 1.0
    assert report["ranking"]["R@5"] == 0.5  # the unshown relevant result was missed
    assert report["matching"]["precision"] == 0.5 and report["matching"]["recall"] == 1.0
