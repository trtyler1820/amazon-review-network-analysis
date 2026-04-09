# Session 9: RAG Stages 1–3 Prep

**Date**: 2026-04-08 ~22:20 ET
**Model**: Claude Sonnet 4.6 / Opus 4.6 (mixed)

---

## User Requests
- Begin RAG Stage 1 (text extraction + metadata prep)
- Goal: everything in place to run embedding overnight
- Later: write Stage 2 + Stage 3 scripts in advance so tonight is just "kick off and go"

## Completed (all in one session)

### Stage 1: Text extraction + metadata

- **`scripts/build_rag_metadata.py`** — Polars re-implementation of `graph_logic/models.py` retention + first_category logic. Writes `data/rag/user_category_metadata.parquet` (50 MB, 2.02M user-category pairs).
- **`scripts/verify_rag_metadata.py`** — Parity check: builds `Graph` from a 500-user sample and compares `is_retained` / `is_observable` / `first_category` against the polars output. `Graph.is_retained` bakes in observable; polars keeps them independent, so the check ANDs them. **Result: 0 mismatches.**
- **`scripts/extract_review_text.py`** — Streams each raw JSONL via `pl.scan_ndjson` + `sink_parquet`. Applies the same filters as `clean_data.py` (`verified_purchase=True`, timestamp in Jan 1–Jul 1 2023 UTC). Resumable (`--force` to re-run, `--only` for single category). Writes to `data/rag/raw_text/{category}.parquet`.
- **`scripts/join_rag_text.py`** — Concats per-category parquets, dedupes on `(user_id, parent_asin, timestamp)`, inner-joins the cleaned CSV on that key to attach `date`/`user_first_date`/`days_since_first`/`review_sequence`, then left-joins `user_category_metadata` to attach `retained`/`observable`/`first_category`. Writes `data/rag/reviews_with_text.parquet`.

| Step | Rows | Time | Output size |
|---|---|---|---|
| Metadata compute (2.5M cleaned → per-user/cat labels) | 2,015,538 pairs | ~1s | 50 MB |
| Parity check (500 users vs. Graph class) | 0 mismatches | ~1s | — |
| Raw text extraction (4 files, 34 GB total raw) | 2,559,785 | 48s | 288 MB |
| Final join + dedup + metadata attach | 2,523,881 | ~2s | 303 MB |

**Per-category final counts:**

| Category | Rows | Retained | Observable | Ret&Obs | Avg text chars |
|---|---:|---:|---:|---:|---:|
| Electronics | 1,540,147 | 295,649 | 1,144,311 | 257,118 | 210 |
| Cell_Phones_and_Accessories | 812,853 | 108,543 | 589,740 | 92,618 | 167 |
| Video_Games | 143,121 | 17,141 | 103,526 | 13,902 | 225 |
| Software | 27,760 | 6,211 | 21,485 | 5,218 | 140 |
| **Total** | **2,523,881** | **427,544** | **1,859,062** | **368,856** | — |

Text length distribution: p50 = 117 chars, p95 = 624 chars.

### Stage 2 + 3 prep (same session)

Installed deps (added to `requirements.txt`):
- `torch==2.11.0`  (MPS available on this Mac)
- `sentence-transformers==5.3.0`
- `qdrant-client==1.17.1`

**`scripts/embed_reviews.py`** — reads `reviews_with_text.parquet`, formats each row as `"title. text"`, encodes with `all-MiniLM-L6-v2` (384-dim, L2-normalized), writes sharded parquets to `data/rag/embeddings/shard_NNNNN.parquet`. Each shard has `point_id` (row index in source) + `embedding` (`list[float32]`). Atomic rename on write so a crash leaves no partial shards. Resumable: existing valid shards skipped on restart. Flags: `--limit`, `--batch-size`, `--device auto/cpu/mps/cuda`, `--shard-size`, `--force`.

**`scripts/index_qdrant.py`** — reads embedding shards + `reviews_with_text.parquet`, joins on `point_id`, creates a local on-disk Qdrant collection at `data/qdrant/`, upserts vectors + payload (`user_id, parent_asin, category_name, rating, date, retained, observable, first_category, title, text`). Includes a smoke query (self-similarity should return score 1.0). Flags: `--limit`, `--recreate`, `--collection`, `--qdrant-path`, `--embeddings-dir`.

### Embedding timing probes (Apple Silicon, MPS)

| Rows | Batch size | Time | Throughput | Full 2.52M ETA |
|---:|---:|---:|---:|---:|
| 10,000 | 128 | 9.7 s | 1,034 r/s | ~41 min |
| 50,000 | 256 | 32.9 s | **1,518 r/s** | **~28 min** |
| 50,000 | 512 | 32.9 s | 1,518 r/s (plateau) | ~28 min |

Sweet spot: `--device mps --batch-size 256`. MPS ceiling hit at 256; larger batches give no gain.

Embedding sanity checks on the 50K probe shard:
- 384-dim float32 vectors
- All L2 norms = 1.0000 (normalization verified)
- Mean abs value ≈ 0.04 (reasonable distribution)
- point_ids 0–49999 (correct row indexing)

### Qdrant dry-run (50K points)

- Upsert throughput: **2,807 points/sec** → full 2.52M ETA ≈ **15 min**
- 50K points on disk: **256 MB** → full 2.52M extrapolation ≈ **~13 GB**
- Smoke query: self-similarity score = 1.0000 (cosine correctness verified)
- Top-3 neighbors semantically coherent (same category, same sentiment)

### Key finding: this is not an overnight job

Revised **total ETA for Stages 2 + 3: ~45 min**, not the 7 hours originally estimated.

The 7h figure assumed CPU-only with a 250 r/s throughput; MPS delivers 6× more on this machine. Full pipeline becomes a lunch-break job.

### Warning surfaced

`Local mode is not recommended for collections with more than 20,000 points.`

Qdrant local mode is functional but query-performance-degraded at scale. Options if it proves too slow at 2.5M:
1. Switch to Docker Qdrant (`docker run -p 6333:6333 qdrant/qdrant`) — same client code, `url="http://localhost:6333"` instead of `path=`.
2. Scale down to observable-only (1.86M rows, -26%) or a stratified sample (~500K).
3. Swap to FAISS for brute-force cosine (no metadata filter support).

Recommend: run full 2.5M locally first and measure. Fall back only if query latency exceeds ~2 s on the dashboard.

## Blockers / Notes
- None; all scripts ready to run.

## Next Steps
1. Kick off full Stage 2 run: `python3 scripts/embed_reviews.py --device mps --batch-size 256` (~28 min).
2. Kick off Stage 3: `python3 scripts/index_qdrant.py --recreate` (~15 min).
3. Measure query latency at 2.5M points; decide Docker vs. local based on what the dashboard needs.
4. Write `rag/query.py` helper: given a natural-language question + metadata filters, return top-k hits + optional LLM synthesis.
