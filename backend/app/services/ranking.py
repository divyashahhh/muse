"""Discovery ranking: fuse relevance signals into one score, then select a diverse top-k.

Signals per candidate (each normalised to 0-1):
- visual:    embedding similarity to the shopper's cropped item (image or, failing that, title),
             mapped through a calibration window so "different category" is ~0 and
             "near-identical" is ~1.
- semantic:  the AI's graded relevance (0-3) for the section the candidate was found under.
- retrieval: Reciprocal Rank Fusion score across queries and sources, rescaled per section.

score = w_visual * visual + w_semantic * semantic + w_retrieval * retrieval, with weights per
section: "Looks like this" is dominated by visual similarity, while aesthetic and brand sections,
which deliberately contain *different* items, lean on semantic relevance. Missing signals have
their weight redistributed, so a quota failure degrades ranking rather than breaking it.

Selection then applies:
- gates: AI grade 0 is dropped; "Looks like this" also drops photos in another category;
- near-duplicate suppression: the same product under another URL or colour page is shown once;
- Maximal Marginal Relevance (Carbonell & Goldstein, 1998) over image embeddings, so a section
  isn't twelve copies of one look: argmax  lambda * score - (1 - lambda) * max_sim_to_selected.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.models import ListingKind
from app.services.embeddings import Similarity, Vector, cosine
from app.services.retrieval import Candidate

# Calibration windows (see app/services/matching.py for the measurements behind them).
IMAGE_WINDOW = (0.60, 0.92)
TEXT_WINDOW = (0.28, 0.50)
# "Looks like this" candidates whose photo is below this are another kind of item.
VISUAL_SECTION_MIN_IMAGE_COSINE = 0.64
NEAR_DUPLICATE_COSINE = 0.975
MMR_LAMBDA = 0.8


@dataclass(frozen=True)
class Weights:
    visual: float
    semantic: float
    retrieval: float


SECTION_WEIGHTS: dict[ListingKind, Weights] = {
    ListingKind.VISUAL_MATCH: Weights(visual=0.55, semantic=0.30, retrieval=0.15),
    ListingKind.AESTHETIC: Weights(visual=0.20, semantic=0.60, retrieval=0.20),
    ListingKind.SIMILAR_BRAND: Weights(visual=0.35, semantic=0.45, retrieval=0.20),
}


@dataclass
class Scored:
    candidate: Candidate
    score: float
    signals: dict[str, float | str | None] = field(default_factory=dict)
    vector: Vector | None = None


def calibrate(similarity: Similarity | None) -> float | None:
    if similarity is None:
        return None
    low, high = IMAGE_WINDOW if similarity.modality == "image" else TEXT_WINDOW
    return min(max((similarity.cosine - low) / (high - low), 0.0), 1.0)


def score_section(
    kind: ListingKind,
    candidates: Sequence[Candidate],
    grades: Sequence[int | None],
    similarities: Sequence[Similarity | None],
) -> list[Scored]:
    """Score one section's candidates and apply relevance gates. Best first."""
    weights = SECTION_WEIGHTS[kind]
    top_rrf = max((c.rrf for c in candidates), default=0.0) or 1.0
    scored: list[Scored] = []
    for candidate, grade, similarity in zip(candidates, grades, similarities, strict=True):
        if grade == 0:
            continue
        if (
            kind == ListingKind.VISUAL_MATCH
            and similarity is not None
            and similarity.modality == "image"
            and similarity.cosine < VISUAL_SECTION_MIN_IMAGE_COSINE
        ):
            continue
        visual = calibrate(similarity)
        semantic = grade / 3 if grade is not None else None
        retrieval = candidate.rrf / top_rrf
        parts = [
            (weights.visual, visual),
            (weights.semantic, semantic),
            (weights.retrieval, retrieval),
        ]
        available = sum(w for w, value in parts if value is not None)
        score = sum(w * value for w, value in parts if value is not None) / available
        scored.append(
            Scored(
                candidate,
                round(score, 4),
                {
                    "visual": _round(visual),
                    "visual_cosine": _round(similarity.cosine if similarity else None),
                    "visual_modality": similarity.modality if similarity else None,
                    "grade": grade,
                    "rrf": round(candidate.rrf, 5),
                    "retrieval": round(retrieval, 4),
                },
                similarity.vector if similarity else None,
            )
        )
    return sorted(scored, key=lambda s: s.score, reverse=True)


def select_diverse(
    scored: Sequence[Scored], k: int, mmr_lambda: float = MMR_LAMBDA
) -> list[Scored]:
    """Top-k by Maximal Marginal Relevance, skipping near-duplicates of anything selected."""
    remaining = list(scored)
    selected: list[Scored] = []
    while remaining and len(selected) < k:
        best, best_value = None, float("-inf")
        for item in remaining:
            redundancy = max((_similarity(item, chosen) for chosen in selected), default=0.0)
            value = mmr_lambda * item.score - (1 - mmr_lambda) * redundancy
            if value > best_value:
                best, best_value = item, value
        assert best is not None
        remaining.remove(best)
        if any(_similarity(best, chosen) >= NEAR_DUPLICATE_COSINE for chosen in selected):
            continue
        selected.append(best)
    return selected


def _similarity(a: Scored, b: Scored) -> float:
    if a.vector is None or b.vector is None or len(a.vector) != len(b.vector):
        return 0.0
    # Title vectors and image vectors aren't comparable for redundancy.
    if a.signals.get("visual_modality") != b.signals.get("visual_modality"):
        return 0.0
    return cosine(a.vector, b.vector)


def _round(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None
