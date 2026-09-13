# Muse

An AI stylist. Show Muse one piece you love — a photo or a product link — pick a store, and it
curates a complete, coherent outfit from that store in the same aesthetic, explaining every pick.
**Price Radar** then compares any item's price across the other stores.

> Portfolio project. Stores are fictional; catalog data comes from a licensed public fashion
> dataset. Nothing here is live inventory or real checkout.

## Status

| Phase | Scope | State |
|---|---|---|
| 1. Foundations | Monorepo, Postgres + pgvector schema & migrations, demo stores, catalog API, frontend shell | ✅ |
| 2. Catalog ingestion | Import licensed dataset, assign items to stores with per-store pricing, CLIP embeddings | Next |
| 3. Aesthetic understanding | Upload / URL input, object storage, vision-LLM aesthetic profile | |
| 4. Curation | Per-slot retrieval + LLM outfit composition with rationales, moodboard view | |
| 5. Price Radar | Cross-store same-product matching, comparison table | |

## Architecture

```
frontend/   React + TypeScript + Tailwind (Vite)     → Vercel
backend/    FastAPI + SQLAlchemy (async) + Alembic   → Railway
            Postgres + pgvector                       → Supabase / Neon
```

### Data model

- **stores** — the fictional retailers.
- **products** — catalog items per store, with a `vector(768)` CLIP image embedding (HNSW, cosine).
  `source_id` is the item's id in the source dataset: the same item can be listed by several stores
  at different prices. It's kept as *ground truth for evaluating* Price Radar and is deliberately
  not used by the matcher.
- **inspirations** — what the user showed Muse (image key in object storage, extracted
  title/price, aesthetic profile, embedding).
- **boards / board_items** — a curated collection: inspiration × store, with an ordered list of
  picks, each with its rationale. The aesthetic profile is snapshotted onto the board so it stays
  reproducible.

### API (so far)

| Method | Path | |
|---|---|---|
| GET | `/api/health` | Liveness + database check |
| GET | `/api/stores` | Stores with product counts |
| GET | `/api/stores/{slug}/products?category=&limit=&offset=` | Paginated catalog |

Interactive docs at `http://localhost:8000/docs`.

## Local development

Requires Python 3.12+, Node 20+, and Postgres with the pgvector extension (Postgres.app ships it;
or `docker compose up -d` — see `docker-compose.yml` for the connection string).

```bash
# Databases (Postgres.app / local Postgres)
createdb muse && createdb muse_test

# Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed_stores
.venv/bin/uvicorn app.main:app --reload        # http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                                     # http://localhost:5173
```

### Checks

```bash
cd backend  && .venv/bin/pytest && .venv/bin/ruff check . && .venv/bin/ruff format --check .
cd frontend && npm run lint && npm run build
```

Backend tests run against `muse_test` (override with `TEST_DATABASE_URL`), building the schema
through the real Alembic migrations.
