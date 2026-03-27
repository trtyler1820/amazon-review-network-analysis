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
| Apr 3, 2026 | Phase 1 (Data Cleaning) | In Progress | Checkpoint deadline |
| Apr 10, 2026 | Phase 2 (Graph Logic) | Pending | Must complete 80%+ tests |
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

- **Phase 1**: Pipeline code complete and verified. Full dataset CSV needs regeneration (current file is sample-only).
- **Phase 2**: Scaffold complete — `graph_logic/` and `tests/` implemented. 54/54 unit tests passing, 92% coverage.
- **Next action**: Run `python3 scripts/clean_data.py` (full run), then activate integration tests in `tests/test_integration.py`.
