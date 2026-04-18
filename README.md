# Amazon Reviews Analysis Dashboard

A full-stack analytics system that models user retention and cross-category expansion patterns from 2.5M Amazon product reviews, combining graph-based behavioral analysis, semantic search over review text, and an interactive dashboard.

> [Pre-recorded demo walkthrough](#) <!-- TODO: Replace with video link -->

---

## Overview

When a user leaves their first Amazon review, what happens next? Do they come back to the same category? Do they branch out into others?

This project treats reviews as a proxy for product engagement and builds a temporal model to answer:

- **Retention**: Which product categories keep users engaged beyond a single interaction?
- **Expansion**: Which entry categories lead users into other high-retention categories?
- **Semantic context**: What are retained users actually saying compared to churned users?

The analysis covers 2.5M verified purchase reviews across four categories (Electronics, Video Games, Software, Cell Phones & Accessories) from January–June 2023, drawn from the [UCSD Amazon Reviews Dataset](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023).

---

## Architecture

```
Raw JSONL (43GB, 4 categories)
        │
        ▼
┌─────────────────┐
│  Data Cleaning   │  Polars streaming: verified purchases, date filter,
│  (clean_data.py) │  dedup by (user, product, timestamp)
└────────┬────────┘
         │  2,523,881 rows
         ▼
┌─────────────────┐     ┌──────────────────┐
│  Graph Logic     │────▶│  ML Layer         │
│  (graph_logic/)  │     │  (ml/)            │
│                  │     │                   │
│  • User/Review   │     │  • Retention RF   │
│    OOP model     │     │  • User clustering│
│  • Retention     │     │  • Feature eng.   │
│    (90-day)      │     │                   │
│  • Expansion     │     └────────┬─────────┘
│    pathways      │              │
│  • Right-        │              │
│    censoring     │              │
└────────┬────────┘              │
         │                        │
         ▼                        ▼
┌─────────────────────────────────────────┐
│  RAG Pipeline                            │
│  (scripts/)                              │
│                                          │
│  Stage 1: Extract text + metadata labels │
│  Stage 2: Embed (all-MiniLM-L6-v2, 384d) │
│  Stage 3: Index into Qdrant              │
│           (100K stratified sample,       │
│            25K per category)             │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  Streamlit Dashboard (web/app.py)        │
│                                          │
│  • Overview (landing page, key findings) │
│  • Semantic Search                       │
│      Qdrant retrieval → Gemini 2.5 Flash │
│      synthesis (Key Themes, Summary,     │
│      Supporting Excerpts)                │
│  • Expansion Pathways (transition matrix,│
│      ExpansionDifference heatmap, graph) │
│  • User Segmentation (K-means clusters + │
│      retention model ROC/importance)     │
│  • Category Detail (rankings + drilldown)│
│  • Limitations                           │
└─────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Tools |
|-------|-------|
| Data processing | Polars (streaming), Pandas |
| Graph modeling | NetworkX (MultiDiGraph + DiGraph) |
| Machine learning | scikit-learn (Random Forest, KMeans), Joblib |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`, 384d), PyTorch (MPS) |
| Vector search | Qdrant (local on-disk, 100K stratified sample) |
| LLM synthesis | Google Gemini 2.5 Flash (via `google-generativeai`) |
| Dashboard | Streamlit, Plotly, matplotlib |
| Startup optimization | `scripts/precompute.py` serializes graph + ML artifacts to `data/precomputed/*.pkl`; cold start ~5–7s |
| Testing | pytest (157 tests across graph, ML, RAG, and web layers) |

## Development Process

### Session Logging

This project was built across 10+ working sessions with AI assistants (Claude Haiku 4.5, Sonnet 4.6, Opus 4.6) and validated with GPT-5.4 Codex audits. Each session is tracked as a standalone markdown file in [`logs/`](logs/), indexed by [`logs/LOG_INDEX.md`](logs/LOG_INDEX.md).

The logging structure was designed for **context efficiency** — each new session starts by reading the index (not all prior logs), picking up exactly where the last session left off. This made it possible to hand off between different models and sessions without losing decisions, rationale, or progress state.

```
logs/
├── LOG_INDEX.md                              # Master index: session table, checkpoints, decisions
├── 2026-03-25_session1_plan-revision-phase1.md
├── 2026-03-27_session3c_audit-organization.md
├── 2026-04-02_session6b_polars-audit-fixes.md
└── ...
```

Each session file records: what was requested, what was completed, blockers encountered, and next steps. The index tracks key checkpoints and an evolving decisions log — creating a full paper trail from raw data to deployed dashboard.

### Custom AI Agents

Two specialized Claude Code agents were created to own distinct layers of the project:

**`uiDev`** (Streamlit Agent) — Owns the dashboard layer in `web/`. Has read-only access to `graph_logic/` and `ml/` as sources of truth, and is responsible for building views, controls, charts, caching, and app flow. It does not redefine backend metrics in the frontend — it surfaces them. Configured with its own persistent memory to track UI decisions across sessions.

**`dScientist`** (Analytics Agent) — Owns the RAG pipeline: review text extraction, embedding, vector indexing, retrieval, and metadata filtering. Operates under the constraint that deterministic analytics stay in Python code — the LLM is only used for retrieval orchestration and synthesis. Treats `graph_logic` as authoritative for behavioral labels and avoids redefining retention or expansion semantics inside the RAG layer.

This separation enforced clean boundaries: the dashboard never recalculates metrics, the RAG pipeline never invents behavioral labels, and each agent has a clear source of truth.

---

## Core Metrics

**Retention** (90-day window):

A user is *retained* if they meet these criteria:
- Left 2 or more reviews
- On 2 or more distinct days within 90 days of their first review in one category
- Users whose first review falls after April 2, 2023 are right-censored (excluded) from retention denominators since their 90-day window extends beyond the dataset boundary.

**Expansion pathway**: Entry category A is a positive expansion pathway to high-retention category B if users who start in A have an above-baseline probability of reviewing in B within 90 days.

```
ExpansionDifference(A → B) = P(B | first = A) − P(B | first ≠ A)
```

**High-retention category**: A category whose retention rate is in the top quartile, with at least 30 observable users.

See [`docs/METRICS.md`](docs/METRICS.md) for complete definitions and worked examples.

---

## Reflections (In Progress)

- Explore methods of token efficiency (JSON vs. TOON, chunking, log index notation) <!-- TODO: Tyler to write reflections after project completion -->
- Start with explicit Agent pipeline instead of having 1 agent do bulk of work and introducing agents mid-way through

---

## Project Structure

```
├── data/
│   ├── raw/                    # Raw JSONL (43GB, not tracked in git)
│   ├── cleaned/                # Cleaned CSV (2.5M rows, not tracked)
│   ├── rag/                    # Embeddings + intermediate parquet (not tracked)
│   └── qdrant_sample/          # 100K-point Qdrant collection (~500MB, not tracked)
├── scripts/                    # Data cleaning + RAG pipeline scripts
├── graph_logic/                # OOP models: User, Category, Review, Graph
│   ├── models.py               # Core classes + retention logic
│   └── analysis.py             # Retention rates, expansion pathways
├── ml/                         # Machine learning layer
│   ├── features.py             # Polars feature engineering
│   └── clustering.py           # KMeans user segmentation
├── web/                        # Streamlit dashboard
├── tests/                      # 157 unit + integration tests
├── docs/                       # Metrics definitions, data specs, reports
├── logs/                       # Per-session development logs
├── notebooks/                  # Data exploration notebooks
└── .claude/agents/             # Custom AI agent definitions
```

---

## Getting Started

### Prerequisites

| Requirement | Detail |
|-------------|--------|
| **Python** | 3.10+ |
| **RAM** | 8GB minimum (sampled Qdrant collection fits in ~500MB); 16GB recommended for full-dataset pipeline |
| **Disk** | ~5GB for the dashboard-only path; ~50GB for the full pipeline (raw JSONL + embeddings + full Qdrant index) |
| **GPU** | Optional. Apple Silicon (MPS) or CUDA reduces embedding time from hours to ~50 minutes |
| **Gemini API key** | Required for Review Search LLM synthesis. Free tier via [Google AI Studio](https://aistudio.google.com/app/apikey) |

### Shared Setup

```bash
git clone https://github.com/trtyler1820/amazon-review-network-analysis.git
cd amazon-review-network-analysis

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root for the Gemini API key (used by the Review Search page):

```bash
echo "GEMINI_API_KEY=your-key-here" > .env
```

> The first time you run Review Search, `sentence-transformers` auto-downloads the `all-MiniLM-L6-v2` model (~90MB) into `~/.cache/huggingface/`. This is a one-time download.

---

### Path A — Dashboard Only (Recommended)

If you just want to explore the dashboard, you need two pre-built artifacts:

1. **`data/cleaned/cleaned_reviews.csv`** — the cleaned 2.5M-row dataset (powers graph, ML, and category pages)
2. **`data/qdrant_sample/`** — the 100K-point stratified Qdrant collection (powers Review Search)

These are not tracked in git. Either regenerate them via Path B, or obtain them from the project owner.

Once they are in place:

```bash
streamlit run web/app.py
```

The first load builds the in-memory graph (~60–120s). Subsequent page navigations are cached.

---

### Path B — Full Pipeline (From Scratch)

#### 1. Download Raw Data (~43GB)

The HuggingFace dataset stores files as `raw_review_{Category}.jsonl`, but the cleaning script expects `{Category}.jsonl` in `data/raw/`. Download and rename in one step:

```bash
python3 -c "
from huggingface_hub import hf_hub_download
import os, shutil
os.makedirs('data/raw', exist_ok=True)
for cat in ['Electronics', 'Video_Games', 'Software', 'Cell_Phones_and_Accessories']:
    src = hf_hub_download(repo_id='McAuley-Lab/Amazon-Reviews-2023',
                          filename=f'raw_review_{cat}.jsonl',
                          repo_type='dataset', local_dir='data/raw')
    shutil.move(src, f'data/raw/{cat}.jsonl')
"
```

#### 2. Run the Pipeline

```bash
# Clean data (43GB → 2.5M rows)
python3 scripts/clean_data.py

# Build RAG corpus (text extraction + metadata join)
python3 scripts/extract_review_text.py
python3 scripts/build_rag_metadata.py
python3 scripts/join_rag_text.py

# Embed reviews (~50 min on Apple Silicon MPS, longer on CPU)
python3 scripts/embed_reviews.py

# Index into Qdrant (~15 min)
#   Default output path: data/qdrant/ (full 2.5M collection, ~12GB)
#   The dashboard reads from data/qdrant_sample/ — override --qdrant-path
#   or rename the directory after indexing.
python3 scripts/index_qdrant.py --recreate

# Verify RAG pipeline
python3 scripts/test_rag_query.py

# Run the test suite (157 tests)
pytest tests/ -v

# Launch dashboard
streamlit run web/app.py
```

> **Note on Qdrant performance.** The full 2.5M-point collection is ~12GB on disk and pushes query latency into the 5+ minute range because the on-disk SQLite backend saturates I/O. The deployed app uses a 100K stratified sample (25K per category) at `data/qdrant_sample/` which keeps query latency to ~5–10 seconds. To reproduce the sample from the full collection, sample 25K rows per category from the joined parquet before embedding, or sample the upsert batch inside `index_qdrant.py`.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

Note: The Amazon review data used in this project is sourced from the [UCSD Amazon Reviews Dataset](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023) and is subject to its own terms of use.

---

<sup>Built as part of coursework for SI 511 (Data Science) and SI 507 (Graph Logic) at the University of Michigan School of Information, Winter 2026.</sup>
