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
| Apr 2, 2026 | ML Layer | ✅ Complete | 107/107 tests; ml/ package with retention + clustering |
| Apr 17, 2026 | Phase 3 (Web Interface) | Pending | 4+ interaction modes required |
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
- **ML Layer**: Complete. `ml/` package added (features.py, retention_model.py, clustering.py). 41 new tests, 107/107 total. 12 notebook cells (38–49) appended for ML analysis. Notebook datetime parsing bugs fixed.
- **Next action**: Phase 3 — build Streamlit web dashboard with 4+ interaction modes.
