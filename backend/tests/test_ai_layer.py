"""Unit tests for the retrieval, ranking, matching and vision stages of the AI layer."""

import io
import json
from decimal import Decimal

import httpx
from google import genai
from google.genai import types
from PIL import Image

from app.models import ListingKind
from app.services.ai import OfferVerdict
from app.services.embeddings import GeminiEmbedder, Similarity, VisualSimilarity
from app.services.imaging import crop_to_box
from app.services.matching import (
    IMAGE_REJECT_BELOW,
    accept_verdict,
    apply_rules,
    brand_conflict,
    model_number_in_title,
    price_notes,
    visual_evidence,
)
from app.services.ranking import calibrate, score_section, select_diverse
from app.services.retrieval import Candidate, canonical_url, reciprocal_rank_fusion
from tests.conftest import ANALYSIS, FakeEmbedder, listing

# --- retrieval ---------------------------------------------------------------------------


def test_canonical_url_strips_tracking_and_presentation() -> None:
    assert canonical_url("https://WWW.Shop.example/p/1/?utm_source=x&size=9#reviews") == (
        "shop.example/p/1?size=9"
    )
    assert canonical_url("https://www.ebay.com/itm/Samba-OG/123456789?_trksid=p1&hash=abc") == (
        "ebay.com/itm/123456789"
    )


def test_rrf_rewards_agreement_across_queries_and_dedupes() -> None:
    a = listing("Shoe A", "https://a.example/1", "A", "10")
    b = listing("Shoe B", "https://b.example/1", "B", "10")
    b_tracked = listing("Shoe B", "https://b.example/1?utm_campaign=z", "B", "10")
    c = listing("Shoe C", "https://c.example/1", "C", "10")
    fused = reciprocal_rank_fusion(
        [("q1", [a, b, c]), ("q2", [b_tracked, c])],
        exclude_urls={"https://c.example/1"},
    )
    # B was found by both queries, so it outranks A's single first place; C is excluded.
    assert [x.listing.title for x in fused] == ["Shoe B", "Shoe A"]
    assert fused[0].rrf == 1 / 62 + 1 / 61
    assert [(q, rank) for q, _, rank in fused[0].hits] == [("q1", 2), ("q2", 1)]


def test_rrf_ranks_each_provider_independently() -> None:
    ebay = listing("Shoe E", "https://ebay.example/1", "eBay", "10", provider="ebay")
    web = [
        listing(f"Shoe {i}", f"https://w.example/{i}", "W", "10", provider="web") for i in range(3)
    ]
    fused = reciprocal_rank_fusion([("q", [*web, ebay])])
    # eBay's first result is rank 1 in its own list, level with the web's first.
    assert fused[0].rrf == fused[1].rrf == 1 / 61


# --- ranking -------------------------------------------------------------------------------


def _candidate(title: str, rrf: float = 1 / 61) -> Candidate:
    return Candidate(listing(title, f"https://s.example/{title}", "S", "10"), rrf=rrf)


def test_calibration_maps_cosine_windows_per_modality() -> None:
    assert calibrate(Similarity(0.55, "image", [])) == 0.0
    assert calibrate(Similarity(0.95, "image", [])) == 1.0
    assert calibrate(Similarity(0.39, "text", [])) == 0.5
    assert calibrate(None) is None


def test_visual_section_is_ordered_by_look_and_gated() -> None:
    candidates = [_candidate("close"), _candidate("far"), _candidate("wrong"), _candidate("junk")]
    scored = score_section(
        ListingKind.VISUAL_MATCH,
        candidates,
        grades=[2, 2, 2, 0],
        similarities=[
            Similarity(0.90, "image", [1.0, 0.0]),
            Similarity(0.72, "image", [0.0, 1.0]),
            Similarity(0.58, "image", [1.0, 1.0]),  # another category entirely
            Similarity(0.95, "image", [1.0, 0.0]),  # graded 0 by the AI
        ],
    )
    assert [s.candidate.listing.title for s in scored] == ["close", "far"]
    assert scored[0].signals["grade"] == 2 and scored[0].signals["visual_modality"] == "image"


def test_missing_signals_redistribute_weight() -> None:
    [only_retrieval] = score_section(
        ListingKind.AESTHETIC, [_candidate("x")], grades=[None], similarities=[None]
    )
    assert only_retrieval.score == 1.0


def test_select_diverse_drops_near_duplicates_and_prefers_variety() -> None:
    candidates = [_candidate("a"), _candidate("a-colour-2"), _candidate("b"), _candidate("c")]
    scored = score_section(
        ListingKind.AESTHETIC,
        candidates,
        grades=[3, 3, 2, 2],
        similarities=[
            Similarity(0.9, "image", [1.0, 0.0, 0.0]),
            Similarity(0.9, "image", [1.0, 0.001, 0.0]),  # same product, another URL
            Similarity(0.9, "image", [0.7, 0.7, 0.0]),  # related but distinct
            Similarity(0.8, "image", [0.0, 0.0, 1.0]),
        ],
    )
    chosen = [s.candidate.listing.title for s in select_diverse(scored, k=3)]
    assert "a-colour-2" not in chosen
    assert chosen[0] == "a" and set(chosen) == {"a", "b", "c"}


# --- matching ------------------------------------------------------------------------------


def test_rules_accept_gtin_and_reject_brand_or_visual_conflicts() -> None:
    same_code = listing("Trainers", "https://x.example/1", "X", "90", gtin="4066748")
    assert apply_rules(ANALYSIS, same_code, reference_gtin="04066748", similarity=None).outcome == (
        "accept"
    )

    other_brand = listing("Samba-style trainers", "https://x.example/2", "X", "30", brand="Nike")
    assert brand_conflict(ANALYSIS, other_brand)
    assert apply_rules(ANALYSIS, other_brand, reference_gtin=None, similarity=None).outcome == (
        "reject"
    )
    # A wrong brand field with the real brand in the title is not a conflict.
    reseller = listing("Adidas Samba OG", "https://x.example/3", "X", "90", brand="Unbranded")
    assert not brand_conflict(ANALYSIS, reseller)

    looks_different = Similarity(IMAGE_REJECT_BELOW - 0.05, "image", [])
    assert (
        apply_rules(ANALYSIS, reseller, reference_gtin=None, similarity=looks_different).outcome
        == "reject"
    )
    # Title similarity is too weak a signal to reject on.
    assert (
        apply_rules(
            ANALYSIS, reseller, reference_gtin=None, similarity=Similarity(0.2, "text", [])
        ).outcome
        == "ai"
    )


def test_model_number_evidence_and_visual_buckets() -> None:
    analysis = ANALYSIS.model_copy(update={"model_number": "IE-3437"})
    assert model_number_in_title(analysis, listing("Samba IE3437", "u", "r", "1")) is True
    assert model_number_in_title(analysis, listing("Samba OG", "u", "r", "1")) is False
    assert model_number_in_title(ANALYSIS, listing("Samba OG", "u", "r", "1")) is None
    assert visual_evidence(Similarity(0.96, "image", [])) == "very_high"
    assert visual_evidence(Similarity(0.72, "image", [])) == "low"
    assert visual_evidence(Similarity(0.47, "text", [])) == "high"
    assert visual_evidence(None) == "unknown"


def test_price_notes_flag_implausibly_cheap_listings() -> None:
    listings = [
        listing("A", "u1", "r", "100"),
        listing("B", "u2", "r", "30"),
        listing("C", "u3", "r", "95"),
    ]
    notes = price_notes(listings, Decimal("100"), "$")
    assert notes[0] is None and notes[2] is None
    assert notes[1] is not None and "70% below" in notes[1]


def test_accept_policy_is_precision_first() -> None:
    def verdict(**changes) -> OfferVerdict:
        base = {
            "index": 0,
            "brand": "match",
            "model": "match",
            "color": "match",
            "verdict": "same_product",
            "confidence": 0.9,
            "reason": "r",
        }
        return OfferVerdict(**{**base, **changes})

    assert accept_verdict(verdict())
    assert accept_verdict(verdict(color="unclear"))
    assert not accept_verdict(verdict(confidence=0.6))
    assert not accept_verdict(verdict(color="mismatch"))
    assert not accept_verdict(verdict(verdict="unsure"))


# --- vision --------------------------------------------------------------------------------


def _jpeg(size: tuple[int, int] = (200, 100)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(out, "JPEG")
    return out.getvalue()


def test_crop_to_box_isolates_the_item_with_padding() -> None:
    cropped = Image.open(io.BytesIO(crop_to_box(_jpeg(), [250, 250, 750, 750])))
    # The box is half of each edge; padding adds 8% of the box's edge on each side.
    assert cropped.size == (116, 58)
    full = _jpeg()
    assert crop_to_box(full, [0, 0, 1000, 1000]) == full  # already a product shot
    assert crop_to_box(full, None) == full
    assert crop_to_box(full, [500, 500, 510, 510]) == full  # implausibly small


async def test_visual_similarity_falls_back_to_titles_and_survives_failures() -> None:
    async def fetch_image(url: str) -> bytes | None:
        return None if "broken" in url else url.encode()

    vision = VisualSimilarity(FakeEmbedder(), fetch_image=fetch_image)
    reference = await FakeEmbedder().embed_texts(["shoe"])
    results = await vision.score(
        reference[0],
        [("https://img/shoe.jpg", "x"), ("https://img/broken.jpg", "denim jacket"), (None, "shoe")],
    )
    assert [r.modality for r in results if r] == ["image", "text", "text"]
    assert results[0].cosine > results[1].cosine

    class Failing(FakeEmbedder):
        async def embed_images(self, images_jpeg):
            raise httpx.ConnectError("down")

    degraded = await VisualSimilarity(Failing(), fetch_image=fetch_image).score(
        reference[0], [("https://img/shoe.jpg", "x")]
    )
    assert degraded == [None]


async def test_gemini_embedder_batches_one_content_per_input() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        count = len(body["requests"])
        return httpx.Response(200, json={"embeddings": [{"values": [0.1, 0.2]}] * count})

    client = genai.Client(
        api_key="test-key",
        http_options=types.HttpOptions(
            httpx_async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )
    embedder = GeminiEmbedder(client, "gemini-embedding-2", 768)
    vectors = await embedder.embed_images([_jpeg()] * 30)
    assert len(vectors) == 30
    assert sorted(len(r["requests"]) for r in requests) == [6, 24]
    first = requests[0]["requests"][0]
    assert first["outputDimensionality"] == 768
    assert first["content"]["parts"][0]["inline_data"]["mime_type"] == "image/jpeg"
