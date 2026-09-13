# Muse

Show Muse one item you love (a photo or a link to a real product) and it:

1. **Discovers** a marketplace of similar items: visual look-alikes, pieces in the same aesthetic,
   and the same kind of item from comparable brands, all real listings from retailers and resellers.
2. **Compares prices** Skyscanner-style: finds the *exact same product* at other retailers,
   verified by AI, sorted cheapest first including shipping.
3. **Saves** anything to a **bag** or **wishlist**. Checkout happens on the retailer's own site.

UI polish is deliberately deferred; this is the working proof of concept.

## How it works

```
 upload / URL ──► fetch page (SSRF-guarded) ──► schema.org / Open Graph product facts
                         │
                         ▼
                 normalise image (Pillow) ──► store (Supabase Storage | local disk)
                         │
                         ▼
     AI vision analysis (Gemini|Claude) ──► identity (brand, model, colourway, category)
                                   + search plan (exact-match query, aesthetic queries,
                                     similar brands)
                         │
        ┌────────────────┴──────────────────┐
        ▼                                   ▼
   DISCOVER                             COMPARE PRICES
   Google Lens visual matches           Google Lens exact matches
   Google Shopping × aesthetic queries   Google Shopping (exact-match query)
   Google Shopping × similar brands     └► Google product store lists (price/shipping/total)
        │                                   │
        │                              dedupe (cheapest per retailer)
        │                                   ▼
        │                              AI verifies "same product?" per listing
        ▼                                   ▼
   listings table (cached per item) ◄───────┘
```

- **Real retailer data, legally sourced.** Search results come from Google Lens and Google
  Shopping through [SerpApi](https://serpapi.com), not by scraping retailer sites. The only page
  Muse fetches directly is the single product link a user pastes.
- **AI where judgement is needed.** A vision model turns an image into a precise identity and
  search plan, and decides which price-comparison results are genuinely the same product rather
  than look-alikes. Providers are swappable via `AI_PROVIDER`: **Google Gemini** (default, free
  tier) or **Anthropic Claude** (`claude-sonnet-5`, paid). Both return schema-validated JSON.
- **Results are cached** per item in Postgres, so reopening an item doesn't spend searches again.
  "Search again" forces a refresh.

### Data model

- **items**: what the user showed Muse: stored image, product-page facts, Claude's analysis.
- **listings**: real listings found for an item, by kind: `visual_match`, `aesthetic`,
  `similar_brand`, `offer` (verified same product, with the match reason).
- **saved_items**: bag and wishlist entries, snapshotted so they survive result refreshes.
  Users are anonymous for now (a per-browser id in the `X-Muse-Client` header).

### API

| Method | Path | |
|---|---|---|
| POST | `/api/items/upload` | Multipart image → analysed item |
| POST | `/api/items/from-url` | `{url}` → analysed item |
| GET | `/api/items/{id}` | Item + analysis |
| POST | `/api/items/{id}/discover?refresh=` | Discovery sections (cached) |
| POST | `/api/items/{id}/prices?refresh=` | Verified offers, cheapest first (cached) |
| GET / POST | `/api/saved` | List / add bag & wishlist items |
| PATCH / DELETE | `/api/saved/{id}` | Move between lists / remove |

Interactive docs: `http://localhost:8000/docs`.

## Setup

### API keys

| Key | For | Required |
|---|---|---|
| `GEMINI_API_KEY` | Item analysis and price-match verification (free: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)) | Yes, or Claude |
| `ANTHROPIC_API_KEY` + `AI_PROVIDER=claude` | Same, using Claude instead (paid) | Optional |
| `SERPAPI_API_KEY` | Google Lens + Shopping results (free plan: 250 searches/month) | Yes |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Public storage for uploads, so visual search works on photos | Recommended |

Without Supabase, uploads are stored on local disk and Google Lens can't see them, so photo
uploads get AI-query results only. Pasted product links always get visual search, because the
retailer's image is already public. Create a **public** bucket named `uploads` in Supabase Storage.

Each item uses roughly 5–8 SerpApi searches for discovery and 3–4 for price comparison.

### Run locally

Requires Python 3.12+, Node 20+ and Postgres.

```bash
createdb muse && createdb muse_test

cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env            # add your API keys
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload         # http://localhost:8000

cd ../frontend
npm install
npm run dev                                      # http://localhost:5173
```

### Checks

```bash
cd backend  && .venv/bin/pytest && .venv/bin/ruff check . && .venv/bin/ruff format --check .
cd frontend && npm run lint && npm run build
```

Backend tests run against `muse_test` (override with `TEST_DATABASE_URL`) using the real Alembic
migrations, with the AI provider, SerpApi and storage replaced by fakes (the Gemini client is
exercised through its real SDK against a mock HTTP transport), so no keys or network are needed.

## Known limitations / next steps

- Some retailers (e.g. Zara) block automated page fetches; users are asked to upload a photo instead.
- Price verification is text-based (titles, retailer, price); adding listing images to the
  verification call would catch colourway mismatches that titles hide.
- Prices mix currencies when results do; the market is set by `SEARCH_COUNTRY`.
- Discovery results aren't re-ranked yet. Next candidates: CLIP embeddings + pgvector for visual
  re-ranking, and Claude filtering of off-aesthetic results.
- Accounts (to sync bag/wishlist across devices), background jobs with progress updates, and UI design.
