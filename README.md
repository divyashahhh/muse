# Muse

Show Muse one item you love (a photo or a link to a real product) and it:

1. **Discovers** a marketplace of similar items: visual look-alikes, pieces in the same aesthetic,
   and the same kind of item from comparable brands, all real listings from retailers and resellers.
2. **Compares prices** Skyscanner-style: finds the *exact same product* at other retailers,
   verified by AI, sorted cheapest first including shipping.
3. **Saves** anything to a **bag** or **wishlist**. Checkout happens on the retailer's own site.

UI polish is deliberately deferred; this is the working proof of concept.

## How it works

Muse runs entirely on free tiers. The AI layer (perception, visual embeddings, rank fusion,
ranking, exact-product matching and evaluation) is documented in depth in
[docs/AI_LAYER.md](docs/AI_LAYER.md).

```
 upload / URL ──► fetch page (SSRF-guarded) ──► schema.org / Open Graph product facts (+ GTIN)
                         │
                         ▼
                 normalise image (Pillow) ──► store (local disk | Supabase Storage)
                         │
                         ▼
          Gemini vision analysis ──► identity (brand, model, colourway, category)
                                     + search plan (exact-match, look-alike and
                                       aesthetic queries, similar brands)
                         │
        ┌────────────────┴──────────────────┐
        ▼                                   ▼
   DISCOVER                             COMPARE PRICES
   eBay Browse API  ┐                   eBay Browse API (query + GTIN)  ┐
   Tavily web search├─► per query       Tavily web search               ├─► candidates
   → product pages  ┘                   → product pages                 ┘
        │                                   │
   Gemini relevance filter             GTIN match ─► accepted
   (drops keyword-search noise)        otherwise Gemini "same product?" check
        │                                   │
        ▼                              cheapest per retailer, sorted by price + shipping
   listings table (cached per item) ◄───────┘
```

- **Real listings, officially sourced.** eBay results come from eBay's public Browse API. Web
  results come from Tavily's search API. Muse then reads each result page itself and keeps it
  only if the retailer's own schema.org data describes a product with a price and image, so
  articles, category pages and blocked sites drop out.
- **Prices are never AI-generated.** They come from eBay's API or the retailer's structured data.
- **AI where judgement is needed.** Gemini (free tier; Claude optional via `AI_PROVIDER`)
  identifies the item and plans searches, filters discovery results for relevance, and checks
  which price-comparison listings are genuinely the same product. A matching barcode (GTIN) is
  accepted without AI.
- **Results are cached** per item in Postgres, so reopening an item doesn't spend quota again.

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

### API keys (all free)

| Key | For | Free tier |
|---|---|---|
| `GEMINI_API_KEY` | Analysis, relevance filtering, same-product checks | [aistudio.google.com/apikey](https://aistudio.google.com/apikey), no card |
| `TAVILY_API_KEY` | Web search for retailer product pages | [app.tavily.com](https://app.tavily.com): 1,000 credits/month, no card |
| `EBAY_CLIENT_ID` + `EBAY_CLIENT_SECRET` | eBay new and pre-owned listings | [developer.ebay.com](https://developer.ebay.com/my/keys): 5,000 calls/day |

Search needs at least one of Tavily or eBay; both give the best coverage. Each item uses about
7 Tavily credits for discovery and 1 for price comparison, and 3 Gemini requests.
`SUPABASE_URL` / `SUPABASE_SERVICE_KEY` are optional (image storage for deployments without a disk).

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
migrations, with the AI provider, search sources and storage replaced by fakes (the Gemini, eBay and
Tavily clients are exercised against mock HTTP transports), so no keys or network are needed.

## Known limitations / next steps

- There's no free reverse image search, so "Looks like this" uses an AI-written visual
  description plus AI filtering rather than pixel similarity. CLIP embeddings could re-rank by
  image similarity later.
- Retailers that block automated access or render prices only with JavaScript (e.g. Zara, H&M,
  Nike) can't be read, so they won't appear in results. eBay covers many of those products.
- Currency depends on the market each site serves (e.g. SGD for a Singapore connection); totals
  across currencies aren't converted.
- Accounts (to sync bag/wishlist across devices), background jobs with progress updates, and UI design.
