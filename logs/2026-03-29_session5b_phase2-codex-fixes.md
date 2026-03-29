# Session 5b: Phase 2 Codex Audit Fixes & Activation

**Date**: 2026-03-29 ~evening
**Model**: Claude Opus 4.6

---

## User Requests
- Implement all findings from Codex audit handoff (session5)
- Activate Phase 2 on real data

## Completed

### High Priority Fixes
- **Right-censoring guard**: Users entering after April 2, 2023 excluded from 90-day retention/expansion denominators (`MAX_ENTRY_DATE` constant). Applied to `User.is_retained()`, `Category.retention_rate`, and `compute_expansion_difference()`.
- **Interaction graph → MultiDiGraph**: Changed from `nx.DiGraph` to `nx.MultiDiGraph` to preserve review-level edge multiplicity. All 2,523,881 reviews now have distinct edges.
- **Transition graph user_count fix**: Changed from counting transition events to tracking distinct user IDs per `(src, dst)` pair.

### Medium Priority Fixes
- **Integration tests activated**: Removed all 17 `@pytest.mark.skip` decorators. Updated expected counts (2,523,881 rows, 1,832,347 users, 369,782 products). Fixed date parsing (`format='ISO8601'`). Added `pytestmark = pytest.mark.slow`.
- **5 spot-check users populated**: Manually verified against CSV covering all retention scenarios (retained, not retained: single review, same day, outside window).
- **Retention cache**: Added `_retention_rate_cache` to `Category` to avoid redundant recomputation.
- **min_cohort_size parameter**: Added to `compute_expansion_difference()` and `compute_all_expansion_pathways()`.
- **Documentation state drift**: Updated README.md, PROJECT_PLAN.md, CLAUDE.md, LOG_INDEX.md, METRICS.md — fixed doc references (`DATA.md` → `data_specs.md`, `DATA_QUALITY_REPORT.md` → `data_quality_report.md`), updated phase statuses, removed "full CSV pending" language.
- **Makefile coverage target**: Now includes integration tests.
- **Slow marker registered** in conftest.py.
- **METRICS.md**: Added right-censoring edge case documentation, scaled back "strong pathway" language to match code.

### Follow-Up Fixes (from TEMP_CLAUDE_GRAPH_LOGIC_FOLLOWUP)
- **Observable user counts aligned with retention denominators**: `generate_summary_report` now shows "observable users" (not total entrants) next to retention rates. `identify_high_retention_categories` uses `observable_user_count()` for min_users threshold.
- **Separated "not retained" from "not observable"**: Added `User.is_observable(category)` method so callers can distinguish unobservable users from genuinely non-retained ones. `is_retained()` docstring clarifies that callers should check `is_observable()` first if the distinction matters.
- **New tests for censoring at category/report layer**: `test_observable_user_count_excludes_late_entrants`, `test_observable_user_count_none_disables_filter`, `test_retention_rate_excludes_unobservable_from_denominator`, `test_is_observable`, `test_min_users_uses_observable_count`, `test_report_shows_observable_users`.
- **Replaced brittle 12-edge transition test**: Changed from `== 12` assertion to `1 <= n_edges <= 12` range check.
- **Cleaned up metric-language drift**: Replaced "strong pathway" with "positive pathway" throughout METRICS.md. Added note that results are raw point estimates.
- **Deleted `TEMP_CLAUDE_GRAPH_LOGIC_FOLLOWUP_2026-03-29.md`** after completing all items.

## Test Results
- **89/89 tests passing** (66 unit + 23 integration)
- **94% coverage** (analysis.py 100%, models.py 91%)
- Wall time: ~48s

## Files Modified
- `graph_logic/models.py` — right-censoring, MultiDiGraph, transition fix, retention cache, `is_observable()` method
- `graph_logic/analysis.py` — right-censoring in expansion, min_cohort_size, observable counts in report/eligibility
- `tests/test_models.py` — 10 new tests (censoring, MultiDiGraph, transition dedup, observability, category denominators)
- `tests/test_analysis.py` — 4 new tests (censoring exclusion, min_cohort, observable eligibility, report semantics)
- `tests/test_integration.py` — full rewrite: activated, spot-checks, new assertions, relaxed transition test
- `tests/conftest.py` — slow marker registration
- `docs/METRICS.md` — observability rule, "positive pathway" language, right-censoring in expansion
- `README.md`, `PROJECT_PLAN.md`, `CLAUDE.md` — status and reference fixes
- `Makefile` — coverage target

## Next Steps
1. Phase 3: Build Streamlit web dashboard with 4+ interaction modes
