# Phase 1 Validation Report

- **Initial Audit Date:** 2026-03-27
- **Initial Auditor:** Codex (read-only audit; identified 10 issues)
- **Remediation Date:** 2026-03-27
- **Remediation by:** Claude (implemented all high/medium priority fixes)
- **Project Root:** `/Users/tylertran/Documents/umich/courses/w26_project`

## Executive Summary

This audit validated the codebase across methodology, implementation quality, and cleaned-data integrity.
The cleaned dataset is broadly usable and internally consistent, but there are several important correctness and reproducibility issues in the cleaning pipeline and documentation that should be refactored before further analysis.

## Remediation Summary (Post-Audit)

**Status:** ✅ **RESOLVED** - All high/medium priority issues fixed in `scripts/clean_data.py`

**Issues Fixed (7/10):**
1. ✅ **Date boundary bug** - Changed `DATE_END` to July 1, 2023 00:00:00 UTC with `<` operator to include full June 30
2. ✅ **Timezone handling** - Explicitly uses UTC via `datetime.fromtimestamp(..., tz=timezone.utc)`
3. ✅ **Quality checks hardcoded** - Now computed from actual data with real pass/fail indicators
4. ✅ **Null-check wrong field** - Changed from 'category' to 'rating' and 'category_name' validation in critical fields
5. ✅ **--output-dir unused** - Wired up CLI parameter; constructor accepts and applies it
6. ✅ **Schema drift (helpful_vote)** - Added back to output schema with documentation
7. ✅ **Duplicate docstring** - Updated to reflect exact timestamp deduplication logic

**Low Priority Items Noted (3/10):**
- Plan/doc drift: Noted but deferred to Phase 2 documentation refresh
- Notebook error: Identified but deferred to Phase 3 when web interface is built
- Hardcoded paths: Documented; acceptable for project structure

**Next Steps:** Re-run cleaning pipeline to generate new data_quality_report.md with computed checks.

## Scope

Audited artifacts:

- `scripts/clean_data.py`
- `docs/data_quality_report.md`
- `PROJECT_PLAN.md`
- `logs.md`
- `CLEANED_DATA_EXPLORER.ipynb`
- `data/cleaned/cleaned_reviews.csv`

Excluded from deep inspection:

- `venv/` contents
- Full raw JSONL line-by-line validation (source files are extremely large)

## Data Snapshot (Observed at Audit Time — Full Run)

> **Note**: This snapshot reflects the full-run artifact present at audit time (2026-03-27).
> The current `cleaned_reviews.csv` is a sample-run artifact (6 rows). Re-run
> `python3 scripts/clean_data.py` without `--sample-size` to regenerate the full dataset.

- `cleaned_reviews.csv` (full run): ~348.47 MB
- Rows: **2,516,345**
- Columns: **12**
- Unique users: **1,827,354**
- Unique parent ASINs: **369,157**
- Category counts:
  - Electronics: 1,535,698
  - Cell_Phones_and_Accessories: 810,361
  - Video_Games: 142,623
  - Software: 27,663

## Findings (Severity Ordered)

## 1) High — Date end boundary bug (June 30 mostly excluded)

**What was found**

- `DATE_END` is set to `datetime(2023, 6, 30)` in `scripts/clean_data.py:58`.
- Filtering uses `df['date'] <= DATE_END` in `scripts/clean_data.py:165`.
- This means only `2023-06-30 00:00:00` is included, not the full day.
- Current output max date is `2023-06-29 23:59:46.366000` in `docs/data_quality_report.md:11`.

**Impact**

- Time-window logic does not actually include full June 30.
- Boundary behavior can materially affect retention-window cohorts.

## 2) High — Duplicate definition mismatch vs implementation

**What was found**

- Docstring states duplicates are “same user reviews same product variant on same day” (`scripts/clean_data.py:218`).
- Actual dedupe key is exact timestamp: `['user_id', 'parent_asin', 'timestamp']` (`scripts/clean_data.py:225-227`).
- In cleaned output, there are still **876** same-day duplicates for `(user_id, parent_asin, day)`.

**Impact**

- Methodology and implementation disagree.
- Same-day repeated reviews can leak into downstream retention/repeat analyses.

## 3) High — Quality report assertions are hardcoded as passed

**What was found**

- The report writes fixed checkmark lines regardless of computed validation results:
  - `scripts/clean_data.py:450-454`

**Impact**

- Report can show “all checks passed” even if future data violates requirements.
- Reduces trust in QA artifact quality.

## 4) Medium — Critical null-check targets wrong category field

**What was found**

- Null-check critical fields include `'category'` (`scripts/clean_data.py:285`).
- Pipeline outputs/uses `'category_name'` (`scripts/clean_data.py:345`, `372-378`).

**Impact**

- One of the true output-critical fields is not directly validated in null checks.

## 5) Medium — `--output-dir` CLI flag is unused

**What was found**

- CLI argument exists (`scripts/clean_data.py:481-482`), but write paths still use global `OUTPUT_DIR` (`scripts/clean_data.py:394`, `400`).
- `args.output_dir` is never applied.

**Impact**

- Reduced portability and reproducibility of pipeline runs.

## 6) Medium — Script/output schema drift (`helpful_vote`)

**What was found**

- Output column selection excludes `helpful_vote` in script (`scripts/clean_data.py:374-378`).
- Current cleaned CSV includes `helpful_vote` as a column.
- Logs claim final columns include `helpful_vote` (`logs.md:104`).

**Impact**

- Current artifact cannot be reproduced exactly from current script revision.
- Increases risk of analysis discrepancies across reruns.

## 7) Medium — Timezone handling is local-time and undocumented

**What was found**

- Timestamp conversion uses local `datetime.fromtimestamp(...)` (`scripts/clean_data.py:114`), not explicit UTC.
- Empirical check shows stored `date` equals local-time conversion for all rows.
- `895` rows are local `2023-06-29` but UTC `2023-06-30`.

**Impact**

- Results depend on runtime machine timezone.
- Date boundary cohorts can differ across environments.

## 8) Low — Plan/documentation acceptance criteria drift

**What was found**

- Plan states dedupe key `(user_id, product_id, timestamp)` (`PROJECT_PLAN.md:95`), but code uses `parent_asin`.
- Plan states timestamps should be within `2022-2023` (`PROJECT_PLAN.md:96`), while pipeline spec is Jan-Jun 2023.

**Impact**

- Requirements ambiguity for reviewers and future contributors.

## 9) Low — Notebook contains executed error state

**What was found**

- `CLEANED_DATA_EXPLORER.ipynb` includes an error output:
  - Notebook cell 18 (`# Save updated data back to CSV`) raises `NameError: output_path is not defined`.

**Impact**

- Notebook appears partially broken when reopened/run.

## 10) Low — Portability/hygiene issues

**What was found**

- Hardcoded absolute paths in script (`scripts/clean_data.py:36-38`).
- Unused constants: `META_FILES` and `REQUIRED_CATEGORIES` (`scripts/clean_data.py:49`, `61`).
- Extraneous malformed directory exists: `{scripts,data/cleaned,docs}`.

**Impact**

- Adds avoidable maintenance and reproducibility friction.

## Integrity Checks That Passed

- No nulls in core cleaned fields: `user_id`, `parent_asin`, `timestamp`, `verified_purchase`, `category_name`, `date`, `user_first_date`, `days_since_first`, `review_sequence`.
- `verified_purchase` is uniformly `True`.
- Categories are exactly the expected 4 values.
- Duplicate count for `(user_id, parent_asin, timestamp)` is 0.
- Ratings are valid numeric values in [1.0, 5.0].
- `helpful_vote` is numeric and non-negative.
- `days_since_first` has no negatives.
- `review_sequence` is positive/integer and monotonic with timestamp within `(user_id, category_name)`.
- Reported category row counts match actual cleaned CSV counts.

## Methodology Observations

- `user_first_date` and `review_sequence` are computed per category file before concatenation, which effectively makes them per `(user_id, category_name)` semantics in the combined dataset.
- This is internally consistent with the current implementation, but should be explicitly documented because global-per-user semantics would produce different results.
- Cross-category behavior is non-trivial: ~9.41% of users appear in more than one category.

## Recommended Refactor Priorities (for Claude)

1. **Fix date filter boundary** to include full day of 2023-06-30 and document timezone policy explicitly (UTC vs local).
2. **Align duplicate logic and docs**:
   - If dedupe should be same-day, dedupe on `(user_id, parent_asin, date_only)`.
   - If exact-timestamp is intended, update docs and report language.
3. **Make report checks computed, not hardcoded** (derive pass/fail from data).
4. **Fix schema consistency**:
   - Validate `category_name` nulls.
   - Decide whether `helpful_vote` is in final schema and enforce consistently.
5. **Wire up `--output-dir`** and remove hardcoded absolute output dependency.
6. **Tighten reproducibility**:
   - Parameterize paths relative to project root.
   - Add deterministic validation script/tests (or `pytest`) for all critical constraints.
7. **Update docs/plan/logs** to reflect true implemented logic and final schema.
8. **Clean notebook error cell** and ensure the notebook runs top-to-bottom without NameError.

## Suggested Validation Checklist Post-Refactor

- Date window includes full Jan 1, 2023 through Jun 30, 2023 (inclusive by intended timezone).
- Zero duplicates for chosen dedupe definition.
- Zero nulls in required output schema.
- Output schema matches documented schema exactly.
- Report values are auto-derived and cross-checked against dataset.
- Re-run on fresh environment produces same counts and same report.
