"""Offline evaluation CLI.

    python -m app.eval template > judgements.jsonl   # every cached result, ready to label
    python -m app.eval score judgements.jsonl         # metrics for the current pipeline output

Label the template by filling in "grade" (discovery, 0-3) or "match" (offers, true/false). After
changing prompts, weights or thresholds, re-run discovery/prices with ?refresh=true for the
judged items and score again: the same judgements then compare pipeline versions.
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.eval.report import ShownListing, evaluate, load_judgements
from app.models import Item, Listing, ListingKind


async def _shown() -> list[tuple[Listing, Item]]:
    async with SessionLocal() as session:
        rows = await session.execute(
            select(Listing, Item).join(Item).order_by(Listing.item_id, Listing.position)
        )
        return list(rows.tuples())


def _kind(listing: Listing) -> str:
    return "offer" if listing.kind == ListingKind.OFFER else "discover"


async def template() -> None:
    for listing, item in await _shown():
        kind = _kind(listing)
        row = {
            "item_id": str(listing.item_id),
            "item": item.analysis.get("product_name"),
            "kind": kind,
            "section": listing.group_label,
            "url": listing.url,
            "title": listing.title,
            "score": listing.score,
            ("grade" if kind == "discover" else "match"): None,
        }
        print(json.dumps(row))


async def score(judgements: list[dict]) -> None:
    shown = [ShownListing(str(x.item_id), _kind(x), x.url, x.position) for x, _ in await _shown()]
    print(json.dumps(evaluate(judgements, shown), indent=2))


def main(argv: list[str]) -> None:
    if argv[:1] == ["template"]:
        asyncio.run(template())
    elif argv[:1] == ["score"] and len(argv) == 2:
        asyncio.run(score(load_judgements(Path(argv[1]).read_text().splitlines())))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
