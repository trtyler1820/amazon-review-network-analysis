# Project Logs Index

Session logs are stored as individual files for token efficiency. Each session gets its own file.

**Naming format**: `YYYY-MM-DD_sessionID_short-description.md`

---

## Session Log Files

| File | Date | Summary |
|------|------|---------|
| [2026-03-25_session1_plan-revision-phase1.md](2026-03-25_session1_plan-revision-phase1.md) | 2026-03-25 | Project plan revision, created clean_data.py, ran full pipeline (2.52M records) |
| [2026-03-26_session2_si507-update.md](2026-03-26_session2_si507-update.md) | 2026-03-26 | Updated docs with SI 507 v2 PDF (expansion formula, graph layers) |
| [2026-03-27_session3_validation-fixes.md](2026-03-27_session3_validation-fixes.md) | 2026-03-27 | Codex audit: fixed 7 issues (date boundary, UTC, quality checks) |
| [2026-03-27_session3b_redline-docs.md](2026-03-27_session3b_redline-docs.md) | 2026-03-27 | Applied 25 Codex redlines to DATA.md, README.md, METRICS.md |
| [2026-03-27_session3c_audit-organization.md](2026-03-27_session3c_audit-organization.md) | 2026-03-27 | Full audit, code fixes, file reorg, log restructure |
| [2026-03-27_session3d_doc-consistency.md](2026-03-27_session3d_doc-consistency.md) | 2026-03-27 | Doc consistency pass: w26_data→data/raw, HuggingFace URL, CLAUDE.md status, artifact disclaimer |
| [2026-03-27_session4_phase2-scaffold.md](2026-03-27_session4_phase2-scaffold.md) | 2026-03-27 | Phase 2 scaffold: graph_logic/ + tests/ — 54/54 passing, 92% coverage |
| [2026-03-29_session5_codex-audit-handoff.md](2026-03-29_session5_codex-audit-handoff.md) | 2026-03-29 | Read-only audit handoff for Claude: Phase 2 correctness fixes, integration test activation, PROJECT_PLAN sync |
| [2026-03-29_session5b_phase2-codex-fixes.md](2026-03-29_session5b_phase2-codex-fixes.md) | 2026-03-29 | Phase 2 activation: Codex fixes, right-censoring, 83/83 tests, 94% coverage |
| [2026-04-02_session6_ml-layer.md](2026-04-02_session6_ml-layer.md) | 2026-04-02 | ML layer added: retention prediction + user clustering, 41 new tests, 107/107 total, 12 notebook cells |
| [2026-04-02_session6b_polars-audit-fixes.md](2026-04-02_session6b_polars-audit-fixes.md) | 2026-04-02 | Polars/Joblib refactor for ml/features.py, fixed 6 audit findings (tied timestamps, user leakage, degenerate labels, etc.), 139/139 tests |
| [2026-04-02_session7_phase3-streamlit.md](2026-04-02_session7_phase3-streamlit.md) | 2026-04-02 | Phase 3: Streamlit dashboard web/app.py — 5 pages (rankings, filter, expansion, detail, ML), streamlit+plotly installed |
| [2026-04-08_session9_rag-stage1-extraction.md](2026-04-08_session9_rag-stage1-extraction.md) | 2026-04-08 | RAG Stages 1–3 prep: text extraction, metadata prep, embedding pipeline setup |
| [2026-04-12_session8_review-search-optimization.md](2026-04-12_session8_review-search-optimization.md) | 2026-04-12 | Review Search optimization: sampled Qdrant (100K), switched to Gemini 2.5 Flash, fixed synthesis truncation |
| [2026-04-16_session10_dashboard-ui-refactor.md](2026-04-16_session10_dashboard-ui-refactor.md) | 2026-04-16 | Dashboard UI refactor: nav reorder, bold active page, Overview + Limitations pages, pp expansion metrics |
| [2026-04-17_session11_doc-finalization.md](2026-04-17_session11_doc-finalization.md) | 2026-04-17 | Doc finalization: README pages/test counts, data_specs variant ratios + row totals, METRICS pp clarification |

---

## Project Infrastructure

| Component | Model | Purpose |
|-----------|-------|---------|
| **Session 1-3 Implementation** | Claude Haiku 4.5 | Data cleaning, testing, documentation |
| **Session 3c+ Implementation** | Claude Sonnet 4.6 / Opus 4.6 | Code audit, fixes, file organization, Phase 2+ |
| **Code Validation & Audit** | GPT-5.3-Codex Extra High Reasoning | Codebase analysis, bug detection |

## Key Checkpoints

| Date | Phase | Status | Notes |
|------|-------|--------|-------|
| Apr 3, 2026 | Phase 1 (Data Cleaning) | ✅ Complete | 2,523,881 rows cleaned |
| Apr 10, 2026 | Phase 2 (Graph Logic) | ✅ Complete | 83/83 tests, 94% coverage |
| Apr 2, 2026 | ML Layer | ✅ Complete | 139/139 tests; Polars/Joblib refactor, 6 audit fixes |
| Apr 17, 2026 | Phase 3 (Web Interface) | ✅ Complete | 6 pages, Review Search with RAG + Gemini synthesis |
| Apr 24, 2026 | Phase 4 (Finalization) | Pending | Final submission deadline |

## Decisions Log

| Date | Decision | Rationale | Status |
|------|----------|-----------|--------|
| 2026-03-25 | Use Jan 2023 - Jun 2023 per SI 507 v2 PDF | Alignment with course requirements | Approved |
| 2026-03-25 | Keep verified_purchase = True filtering | Ensures actual buyer data | Confirmed |
| 2026-03-25 | Group by parent_asin, not individual ASIN | Deduplicates variants | Confirmed |
| 2026-03-27 | Split logs into per-session files | Token efficiency for Claude context | Confirmed |

## Current Status

- **Phase 1**: Complete. Full cleaned dataset: 2,523,881 rows, 1,832,347 users, 369,782 products.
- **Phase 2**: Complete. All Codex audit findings implemented. 83/83 tests passing, 94% coverage. Right-censoring, MultiDiGraph, transition fix, 5 spot-checks verified.
- **ML Layer**: Complete. `ml/` package with Polars/Joblib refactor. 6 audit findings fixed (tied timestamps, user leakage, degenerate labels, censoring tests, pinned integration assertions). 139/139 tests passing.
- **Phase 3**: Complete. `web/app.py` — 6 pages (Overview, Semantic Search, Expansion Pathways, User Segmentation, Category Detail, Limitations). Nav uses bold-active button pattern. Overview is default landing page with top-line metrics, retention headline, and pp-corrected expansion summary. Semantic Search uses Qdrant (100K sample) + Gemini 2.5 Flash synthesis.
- **Next action**: Phase 4 — finalize docs, clean up, full test suite check. Deadline April 24, 2026.
