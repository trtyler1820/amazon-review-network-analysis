# Session 12: Precompute for Streamlit Fast Start

**Date**: 2026-04-17 ~22:30 ET
**Model**: Claude Sonnet 4.6

---

## User Requests
- Can network analysis be hardcoded rather than recomputed on every Streamlit open?
- What else can be hardcoded?
- Approved implementing the full pre-computation strategy (graph + expansion + ML).

## Completed
- **`scripts/precompute.py`**: 3-stage serializer.
  - Step 1 — Build Graph from CSV, prime `Category._retention_rate_cache`, strip `interaction_graph` (2.2M nodes / 2.5M edges removed for pickle — halves file size with no UI impact).
  - Step 2 — Compute expansion artifacts (`high_ret`, `count_matrix`, `diff_matrix`).
  - Step 3 — Run ML pipeline (features → k-search → KMeans fit → cluster profiles).
- **`web/app.py`**: each `@st.cache_resource` loader now checks `data/precomputed/*.pkl` first and falls back to live compute if missing. `load_graph()` returns `(graph, build_time, source)` where source ∈ {"precomputed", "csv"}. Startup status box reads "Loading precomputed data..." when pickles are present.
- **`.gitignore`**: added `data/precomputed/` (large artifacts, regenerated on demand).
- **Smoke test (port 8601)**: server healthy in 1s, root HTTP 200 in 1 ms.
- **Standalone unpickle timing**: graph 4.04s + ml 0.89s + expansion 0.002s = **4.93s**; post-load metric reads for all 4 categories in 0.51s.

## Artifact sizes
- `graph.pkl` — 366 MB (1,832,347 users, 4 categories, 12 transition edges; interaction layer stripped)
- `expansion.pkl` — 1.2 KB (`high_ret = ['Software']`)
- `ml.pkl` — 217 MB (best_k = 2, 12 features, MiniBatchKMeans)

## Blockers / Notes
- Fallback is intentional — pickles are a speed optimization, not a correctness dependency. If `data/precomputed/` is empty (fresh clone, post-CSV refresh), the app recomputes live exactly as before.
- Regenerate pickles after any edit to `graph_logic/`, `ml/`, or the cleaned CSV:

  ```bash
  python3 scripts/precompute.py
  ```

- Cold-start wall time: **~90–180s → ~5–7s** (factor of ~20–30x).

## Next Steps
1. Phase 4 finalization — docs, README update mentioning precompute script.
2. Optional: invalidate pickles via file mtime check vs. CSV mtime if desired (not done; manual regen is fine for this scope).
