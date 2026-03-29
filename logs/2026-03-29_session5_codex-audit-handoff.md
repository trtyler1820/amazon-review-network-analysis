# Session 5: Codex Audit Handoff

**Date**: 2026-03-29
**Model**: GPT-5 Codex

---

## User Request

- Perform a read-only audit of the current codebase.
- Check whether `PROJECT_PLAN.md` is up to date.
- Create a handoff document in `logs/` for Claude to implement the findings.

## Scope Reviewed

- `scripts/clean_data.py`
- `graph_logic/models.py`
- `graph_logic/analysis.py`
- `tests/`
- `README.md`
- `PROJECT_PLAN.md`
- `CLAUDE.md`
- `docs/METRICS.md`
- `docs/data_specs.md`
- `docs/data_quality_report.md`
- `docs/phase1_data_integrity_report.md`
- `logs/LOG_INDEX.md`

## Executive Summary

The repo is materially further along than some documentation claims. A full cleaned artifact exists in `data/cleaned/cleaned_reviews.csv`, and the data quality report reflects a full run dated 2026-03-28. However, there are still implementation-level correctness issues in the Phase 2 graph/metric layer and status drift across project docs.

The highest-priority work is not "run the full CSV" anymore. The highest-priority work is to fix metric correctness and validation gaps before using the graph outputs as evidence for product or strategy conclusions.

## Findings For Claude To Implement

### 1. High Priority: Handle right-censoring in retention and expansion logic

**Problem**
- Users entering too close to `2023-06-30` do not have a full 90-day observation window.
- Current logic still includes them in denominators for retention and expansion.

**Files**
- `graph_logic/models.py`
- `graph_logic/analysis.py`
- `docs/METRICS.md`
- `docs/data_specs.md`

**Why it matters**
- This will bias retention and pathway rates downward.
- It is a methodology issue, not just a documentation issue.

**Implementation target**
- Define an explicit observability rule for 90-day analyses.
- Likely policy: exclude users whose first relevant review occurs after `2023-04-01 00:00:00 UTC` from 90-day denominators.
- Apply this consistently to:
  - category retention denominators
  - expansion pathway cohorts
- Document the rule clearly in `docs/METRICS.md` and `docs/data_specs.md`.
- Add tests covering included vs excluded late entrants.

### 2. High Priority: Fix interaction graph edge semantics

**Problem**
- `interaction_graph` is documented as review-level, but it is implemented as `nx.DiGraph`.
- Multiple reviews from one user to the same `parent_asin` collapse into one edge.
- Edge attributes for earlier reviews can be overwritten by later ones.

**Files**
- `graph_logic/models.py`
- `tests/test_models.py`
- `tests/test_integration.py`
- `docs/METRICS.md` or `CLAUDE.md` if graph semantics are described there

**Why it matters**
- The graph currently does not preserve review-level edge multiplicity.
- Any analysis based on edge count or review sequence at the graph layer can be wrong.

**Implementation target**
- Decide whether Layer 1 should be:
  - a true review-level multigraph, or
  - an aggregated user-product graph with explicit aggregate edge attributes.
- Update implementation and docs so they match exactly.
- Add tests proving repeated reviews do not silently collapse unless that is the intended design.

### 3. High Priority: Fix transition graph user counts

**Problem**
- Transition edges claim `user_count = number of distinct users making the transition`.
- Current implementation increments counts multiple times when one user leaves multiple later reviews in the destination category.

**Files**
- `graph_logic/models.py`
- `tests/test_models.py`
- `tests/test_integration.py`

**Why it matters**
- Transition graph weights are not currently trustworthy as user-level counts.

**Implementation target**
- Count each `(user, source_category, dest_category)` transition at most once.
- Add tests where one user reviews the destination category multiple times and still contributes only one transition count.

### 4. Medium Priority: Activate and repair integration tests

**Problem**
- `tests/test_integration.py` still assumes the full dataset is unavailable.
- All tests are skipped.
- Expected counts are stale relative to the current checked-in full-run report.

**Files**
- `tests/test_integration.py`
- `docs/data_quality_report.md`

**Current observed artifact**
- `docs/data_quality_report.md` reports:
  - rows: `2,523,881`
  - users: `1,832,347`
  - products: `369,782`
- `wc -l data/cleaned/cleaned_reviews.csv` returned `2,523,882` lines including header

**Implementation target**
- Update expected counts to current authoritative values.
- Remove stale "tonight/full run pending" language.
- Unskip tests once expectations are valid.
- Add a clear lightweight strategy if some tests are too expensive for routine local runs.
- Populate manual spot-check cases if that requirement is still intended to be enforced.

### 5. Medium Priority: Resolve documentation state drift

**Problem**
- Some docs still describe the repo as if Phase 2 has not started or the full CSV does not exist.
- Some docs refer to outdated filenames such as `DATA.md`.

**Files**
- `README.md`
- `PROJECT_PLAN.md`
- `CLAUDE.md`
- `logs/LOG_INDEX.md`

**Examples**
- `README.md` says Phase 2 is "Ready to Start" even though `graph_logic/` and `tests/` exist.
- `CLAUDE.md` says Phase 2 is ready to start and full CSV is pending.
- `PROJECT_PLAN.md` still says cleaned output is sample-only/full run pending.
- Multiple files still refer to `docs/DATA.md` although the current file is `docs/data_specs.md`.

**Implementation target**
- Make repo state claims consistent with the actual checked-in artifact set.
- Update doc references to current filenames.
- Distinguish clearly between:
  - code scaffold complete
  - verified against full artifact
  - methodology complete

### 6. Medium Priority: Align implementation with pathway robustness language

**Problem**
- `docs/METRICS.md` recommends cohort-size and uncertainty checks for "strong pathway" language.
- The code currently computes only raw differences.

**Files**
- `graph_logic/analysis.py`
- `docs/METRICS.md`
- `README.md` if it interprets pathway outputs

**Why it matters**
- If the project will make product/strategy interpretations, raw differences alone are too weak.

**Implementation target**
- Either:
  - implement the robustness checks described in the doc, or
  - scale back the documentation so it matches current code.
- Do not leave a "strong pathway" label in docs unless the code supports the claimed standard.

## PROJECT_PLAN.md Status

`PROJECT_PLAN.md` is partially current but not up to date enough to act as a reliable source of truth.

### Still correct

- Phase 2 scaffold exists.
- `graph_logic/` and `tests/` are present.
- "54 tests" is structurally plausible from the unit test files.

### Out of date

- It still claims the full CSV is pending.
- It still claims the cleaned artifact is sample-only.
- It frames integration-test blockage as missing full data, when the real blockers are skipped tests, stale expectations, and missing spot checks.
- It still uses outdated doc names like `DATA.md`.

### Required plan updates

- Replace "full CSV pending" with the current full-run state.
- Update the remaining work list to focus on:
  - right-censoring fix
  - graph correctness fixes
  - integration test activation
  - manual validation on real users
  - documentation sync

## Suggested Implementation Order For Claude

1. Fix methodology correctness first:
   - right-censoring
   - transition counting
   - interaction graph semantics
2. Add or update tests for those behaviors.
3. Repair and activate integration tests against the current full-run artifact.
4. Update `PROJECT_PLAN.md`, `README.md`, `CLAUDE.md`, and `logs/LOG_INDEX.md` so status matches reality.
5. Only after that, treat Phase 2 outputs as ready for interpretation or Phase 3 visualization.

## Acceptance Criteria For This Handoff

- Retention and expansion denominators exclude unobservable late entrants, or another explicit policy is implemented and documented.
- Transition graph `user_count` reflects distinct users, not repeated reviews by the same user.
- Interaction graph semantics are explicit and enforced by tests.
- Integration tests are no longer stale by construction.
- `PROJECT_PLAN.md` reflects current artifact reality and current blockers.
- Repo docs consistently reference `docs/data_specs.md` instead of removed/older names.

## Notes

- This handoff is based on a read-only audit only.
- No code or tests were executed as part of the audit.
- No attempt was made to modify user-authored work outside creation of this handoff log.
