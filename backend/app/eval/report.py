"""Score cached pipeline output against a judgement file.

Judgements are JSON lines, one per (item, listing URL):
    {"item_id": "...", "kind": "discover", "url": "...", "grade": 0-3}
    {"item_id": "...", "kind": "offer", "url": "...", "match": true}

Grades: 3 excellent, 2 good (relevant), 1 marginal, 0 wrong. Unjudged discovery results count
as grade 0, which is conservative; `judged@k` reports how complete the judgements are.
"""

import json
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.eval.metrics import (
    average_precision,
    match_scores,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.services.retrieval import canonical_url

CUTOFFS = (5, 10)


@dataclass(frozen=True)
class ShownListing:
    item_id: str
    kind: str  # "discover" for every discovery section, or "offer"
    url: str
    position: int


def load_judgements(lines: Iterable[str]) -> list[dict]:
    return [json.loads(line) for line in lines if line.strip()]


def evaluate(judgements: Sequence[dict], shown: Sequence[ShownListing]) -> dict:
    """Mean metrics over items, for discovery ranking and offer matching."""
    grades: dict[str, dict[str, int]] = defaultdict(dict)
    matches: dict[str, dict[str, bool]] = defaultdict(dict)
    for j in judgements:
        url = canonical_url(j["url"])
        if j["kind"] == "discover" and j.get("grade") is not None:
            grades[j["item_id"]][url] = int(j["grade"])
        elif j["kind"] == "offer" and j.get("match") is not None:
            matches[j["item_id"]][url] = bool(j["match"])

    by_item: dict[tuple[str, str], list[ShownListing]] = defaultdict(list)
    for listing in shown:
        by_item[(listing.item_id, listing.kind)].append(listing)

    ranking: dict[str, list[float]] = defaultdict(list)
    for item_id, judged in grades.items():
        results = sorted(by_item.get((item_id, "discover"), []), key=lambda x: x.position)
        urls = [canonical_url(x.url) for x in results]
        ranked = [judged.get(url, 0) for url in urls]
        relevant = sum(g >= 2 for g in judged.values())
        ranking["MRR"].append(reciprocal_rank(ranked))
        ranking["MAP"].append(average_precision(ranked, relevant))
        for k in CUTOFFS:
            ranking[f"P@{k}"].append(precision_at_k(ranked, k))
            ranking[f"R@{k}"].append(recall_at_k(ranked, relevant, k))
            ranking[f"nDCG@{k}"].append(ndcg_at_k(ranked, k, list(judged.values())))
            ranking[f"judged@{k}"].append(
                sum(url in judged for url in urls[:k]) / min(k, len(urls)) if urls else 0.0
            )

    matching: dict[str, float] = {}
    if matches:
        # Pairs are (item, listing): the same retailer URL can be judged for different items.
        scores = match_scores(
            {
                f"{x.item_id} {canonical_url(x.url)}"
                for x in shown
                if x.kind == "offer" and x.item_id in matches
            },
            {f"{item} {u}" for item, labels in matches.items() for u, m in labels.items() if m},
            {f"{item} {u}" for item, labels in matches.items() for u in labels},
        )
        matching = {
            "precision": scores.precision,
            "recall": scores.recall,
            "F1": scores.f1,
            "TP": scores.true_positives,
            "FP": scores.false_positives,
            "FN": scores.false_negatives,
        }

    return {
        "items_judged": {"discover": len(grades), "offer": len(matches)},
        "ranking": {name: round(statistics.fmean(v), 4) for name, v in sorted(ranking.items())},
        "matching": {k: round(v, 4) if isinstance(v, float) else v for k, v in matching.items()},
    }
