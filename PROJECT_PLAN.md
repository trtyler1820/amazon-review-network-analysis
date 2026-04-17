# Amazon Reviews Analysis Project Plan

**Project**: Graph-based analysis of Amazon review data for retention and expansion patterns
**Courses**: SI 511 (Data Science), SI 507 (Graph Logic)
**Student**: Tyler Tran
**Deadline**: April 24, 2026
**Checkpoint**: April 3, 2026
**Status**: Phase 1 complete. Phase 2 complete (83/83 tests passing). ML layer added (107/107 tests). Phase 3 next.

---

## Executive Summary

Build an interactive analysis system to understand user retention and cross-category expansion patterns in Amazon reviews. The project emphasizes data cleaning (SI 511) and graph-based analysis (SI 507) with a web interface for exploration. Simplified scope from original 5-phase plan: focused on cleaning → graph → web (no separate database layer).

**Key Questions**:
- Which product categories are strong customer entry points?
- Which categories effectively retain users?
- Which entry categories lead to cross-category exploration?
- Which categories attract but fail to retain users?
- What distinct reviewer archetypes exist in the data? *(ML: user segmentation)*

---

## Key Dates & Milestones

| Date | Milestone | Status |
|------|-----------|--------|
| April 3, 2026 | **CHECKPOINT**: Phase 1 complete (cleaned dataset ready) | ✅ Complete — 2,523,881 rows cleaned |
| April 10, 2026 | Phase 2 complete (graph logic & tests working) | ✅ Complete — 83/83 tests, right-censoring, spot-checks |
| April 10, 2026 | ML layer added (user clustering) | ✅ Complete — clustering pipeline, tests passing |
| April 17, 2026 | Phase 3 complete (web interface functional) | ⏱️ Pending |
| April 24, 2026 | Final submission (all phases complete) | ⏱️ Pending |

---

## Data Specification

**Source**: UCSD Amazon reviews dataset (already downloaded to `data/raw/`)
**Time Period**: January 2023 - June 2023 (per SI 507 v2 PDF - full 6-month observation window)
**Categories**: 4 exact categories (per SI 507 v2 PDF):
  1. Electronics
  2. Video Games
  3. Software
  4. Cell Phones and Accessories
**Filtering**:
- `verified_purchase = true` only (ensures actual buyer data; row count impact to document)
- Group by `parent_asin` (not individual ASIN variants - deduplicates color/size variants)

**Record Types**:
- Individual reviews: `user_id`, `product_id`, `parent_asin`, `category`, `timestamp`, `rating`, brand, metadata
- Derived fields: user first date, days since first review, review sequence number

**Scale**: 50M+ rows expected (tech categories have high volume)

---

## Critical Metrics

### Retention
A user is **retained** in a category if:
- Within 90 days of their first review in that category
- They post 2+ reviews on at least 2 distinct days

**Retention Rate** = retained_observable_users / total_observable_users_in_category

(Observable = first review in category on or before MAX_ENTRY_DATE = 2023-04-02; right-censored users excluded.)

### Expansion Pathway
An entry category is a strong expansion pathway if users whose first reviewed category is A have an above-baseline probability of later reviewing a high-retention category B within 90 days.

**Formula**: ExpansionDifference A→B = P(B within 90d | first category = A) − P(B within 90d | first category ≠ A)

**Baseline** = Probability of entering high-retention category B for users whose first entry was NOT in A

### High-Retention Categories
Categories in the top quartile by retention rate (with minimum 30+ users) - ideal entry points for new customers.

---

## Project Phases

### Phase 1: SI 511 Data Cleaning (Vibing/Coding)
**Timeline**: Now → April 3, 2026
**Objectives**:
- [ ] Assess data quality in `data/raw/` files
- [ ] Build cleaning pipeline (duplicates, nulls, validation, standardization)
- [ ] Derive columns for retention analysis (user first date, days since, review sequence)
- [ ] Export cleaned dataset (CSV/Parquet)
- [ ] Document data limitations and cleaning decisions

**Deliverables**:
- `scripts/clean_data.py` - Cleaning pipeline
- `data/cleaned/` - Processed dataset
- Data quality report (issues found & resolved)
- Schema documentation

**Acceptance Criteria**:
- ✓ No duplicate (user_id, parent_asin, timestamp) combinations
- ✓ All timestamps valid and within Jan-Jun 2023 range
- ✓ No critical null values
- ✓ Categories standardized; verified_purchase = true filter applied
- ✓ Grouped by parent_asin (not individual ASIN)
- ✓ Row counts documented (before/after cleaning)
- ✓ Retention pool size validated (decide if threshold adjustment needed)

---

### Phase 2: SI 507 Graph Logic & Testing (Python Programming)
**Timeline**: April 4 → April 10, 2026
**Objectives**:
- [ ] Design and implement graph data structure (User, Category, Review, Graph classes)
- [ ] Build retention calculation engine (per-user, per-category)
- [ ] Identify high-retention categories (top quartile, min user threshold)
- [ ] Analyze expansion pathways (baseline vs. conditional probabilities)
- [ ] Write comprehensive test suite (unit + integration tests)
- [ ] Generate analysis summary (category rankings, expansion pathways, stats)

**Deliverables**:
- `graph_logic/models.py` - Core OOP classes
- `graph_logic/analysis.py` - Retention & expansion calculations
- `tests/` - Unit and integration tests (80%+ coverage target)
- Summary report: category rankings, expansion patterns, key statistics

**Acceptance Criteria**:
- ✓ Retention calculations manually verified on 5+ sample users
- ✓ Graph structure validated (node/edge counts match cleaned data)
- ✓ All 90-day windows calculated correctly
- ✓ Edge cases handled (1-review users, categories <30 users)
- ✓ Tests passing; code reviewable
- ✓ Handles 50M+ rows without critical errors

---

### Phase 3: SI 511 Web Interface (Web Development)
**Timeline**: April 11 → April 17, 2026
**Objectives**:
- [ ] Choose and set up web framework (Streamlit recommended)
- [ ] Build interactive dashboard
- [ ] Implement category explorer (retention rates, user counts)
- [ ] Visualize expansion pathways (network or Sankey diagram)
- [ ] Add filtering/sorting controls
- [ ] Ensure responsive performance

**Core Interactions** (4+ required):
1. View category rankings by retention rate
2. Filter categories by metrics (user count, retention rate)
3. Explore expansion pathways (entry → downstream categories)
4. Inspect individual category details

**Deliverables**:
- `web/app.py` - Streamlit application
- Visualizations: retention bar charts, category network graph, Sankey diagram
- Responsive interface with filters and controls

**Acceptance Criteria**:
- ✓ All views load without errors
- ✓ Filters and sorting work correctly
- ✓ Metrics match Phase 2 calculations
- ✓ Interface responsive and performs well
- ✓ Unfamiliar users can understand navigation

---

### Phase 4: Finalization & Submission
**Timeline**: April 18 → April 24, 2026
**Objectives**:
- [ ] Organize code structure and clean up
- [ ] Complete all documentation (README, data_specs.md, METRICS.md)
- [ ] Run full test suite
- [ ] Performance optimization if needed
- [ ] Final code review

**File Structure**:
```
/data/
  /raw/              - Downloaded review data (JSONL files)
  /cleaned/          - Processed dataset
/graph_logic/
  __init__.py
  models.py          - User, Category, Review, Graph classes
  analysis.py        - Retention & expansion calculations
/ml/
  __init__.py
  features.py        - Feature engineering (Graph → DataFrames)
  clustering.py      - K-means user segmentation pipeline
/web/
  app.py             - Streamlit dashboard
/tests/
  test_models.py
  test_analysis.py
  test_integration.py
  test_ml_features.py
  test_ml_clustering.py
/docs/
  data_specs.md      - Data spec & cleaning notes
  METRICS.md         - Retention/expansion definitions
PROJECT_PLAN.md      - High-level overview
README.md            - Getting started guide
```

**Acceptance Criteria**:
- ✓ All tests passing (80%+ coverage)
- ✓ Documentation complete and accurate
- ✓ No critical bugs or edge case failures
- ✓ Code organized and reviewed
- ✓ Ready for submission

---

## Tech Stack (TBD - Subject to Change)

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Data Processing** | Python, pandas (or Polars/PySpark if memory issues) | Start with pandas; switch if hitting RAM limits |
| **Graph Analysis** | NetworkX or custom implementation | Depends on query patterns and memory constraints |
| **Visualization** | Plotly / Matplotlib / Seaborn | Integrated in Streamlit app |
| **Web Interface** | Streamlit (recommended) | Fast prototyping; interactive by default |
| **Testing** | pytest | Standard Python testing framework |
| **Version Control** | Git + GitHub | Track progress and changes |

---

## Success Criteria (Grading Rubric)

✓ Data cleaning thorough, well-documented, and validated
✓ Retention calculations manually verified on 5+ sample users
✓ Graph structure correctly represents user-category relationships and handles 50M+ rows
✓ Expansion pathway analysis accurate and meaningful
✓ Web interface intuitive with 4+ interaction modes (required for SI 507)
✓ OOP design with User, Category, Review, Graph classes (SI 507 requirement)
✓ Real data analysis (Amazon reviews filtered by verified_purchase = true)
✓ 80%+ test coverage with passing unit/integration tests
✓ Complete documentation (data_specs.md, METRICS.md, README)
✓ Meets SI 507 final project requirements:
  - Graph/network structure ✓
  - Object-oriented design ✓
  - Real data (Amazon reviews) ✓
  - 4+ interaction modes ✓
  - Web interface (Streamlit) ✓
  - Comprehensive testing ✓

---

## Progress Tracking

### Phase 1: Data Cleaning (SI 511)
- [x] Data files from `data/raw/` assessed
- [x] Data quality issues identified
- [x] Cleaning pipeline built and tested (`scripts/clean_data.py`)
- [x] Derived columns created (user first date, days since, sequence)
- [x] Cleaned dataset exported — `data/cleaned/cleaned_reviews.csv` (2,523,881 rows)
- [x] Quality report generated (`docs/data_quality_report.md`, `docs/phase1_data_integrity_report.md`)
- [x] Retention pool size validated on full dataset

### Phase 2: Graph Logic & Testing (SI 507)
- [x] Graph data structure designed
- [x] User, Category, Review, Graph classes implemented (`graph_logic/models.py`)
- [x] Retention calculation engine built (`graph_logic/analysis.py`)
- [x] Right-censoring guard implemented (excludes late entrants from 90-day denominators)
- [x] High-retention categories identification implemented
- [x] Expansion pathway analysis implemented (conditional probability difference formula)
- [x] Interaction graph: MultiDiGraph preserving review-level edge multiplicity
- [x] Transition graph: distinct user counts per category transition
- [x] Unit tests — 60/60 passing (`tests/test_models.py`, `tests/test_analysis.py`)
- [x] Integration tests — 23/23 passing (`tests/test_integration.py`)
- [x] Retention calculations manually verified on 5 real users (spot-checks)
- [x] Summary report generated on full dataset

### ML Layer (Extends Phase 2)
- [x] Feature engineering from Graph objects (`ml/features.py`)
  - `build_user_features(graph, min_reviews)` — 12 global features per user for clustering
- [x] User segmentation (`ml/clustering.py`)
  - MiniBatchKMeans (scales to 1.8M users)
  - Elbow + silhouette analysis with subsampling (200K) for k selection
  - Human-readable cluster labels: One-and-done, Casual reviewer, Loyal returner, Power reviewer, Category explorer, Power explorer
- [x] Tests — passing (`tests/test_ml_features.py`, `tests/test_ml_clustering.py`)
- [x] Notebook cells added to `notebooks/analysis.ipynb`

### Phase 3: Web Interface (SI 511)
- [ ] Web framework selected and set up
- [ ] Dashboard view implemented
- [ ] Category explorer built
- [ ] Expansion pathway visualization added
- [ ] Filters and sorting implemented
- [ ] Interface tested and responsive

### Phase 4: Finalization
- [ ] All code organized and cleaned up
- [ ] Documentation complete (data_specs.md, METRICS.md, README)
- [ ] Full test suite passing
- [ ] Performance optimized
- [ ] Final review done
- [ ] Ready to submit ✓

---

## Key Considerations & Decisions

### Data Volume & Memory
- Tech categories may have 50M+ rows
- Start with Pandas; switch to Polars/PySpark/DuckDB if hitting RAM limits
- Monitor retention pool size early (most users only leave 1 review)

### Retention Threshold
- Definition: 2+ reviews on 2+ distinct days within 90 days of first review
- Validate feasibility early — may need adjustment if pool shrinks to <5% of users
- Alternatives if needed: extend window to 180 days, relax "2 distinct days" constraint

### Data Preprocessing
- Filter by `verified_purchase = true` only (ensures actual buyer data; document row count impact)
- Filter by date range: January 1, 2023 - June 30, 2023 (per SI 507 v2 PDF)
- Group by `parent_asin` (not individual ASIN variants) to deduplicate color/size variants
- Filter to 4 required categories: Electronics, Video Games, Software, Cell Phones and Accessories

### Technology Choices
- Data processing: Start with pandas, evaluate Polars/PySpark if needed
- Graph: NetworkX or custom implementation (depends on query patterns)
- Web: Streamlit for rapid prototyping and interactivity
- Testing: pytest with 80%+ coverage target

---

## Notes & Observations

```
[2026-03-25] - Project Scope Revised
- Removed SI 564 (database layer); focusing on SI 511 (data + web) + SI 507 (graph + tests)
- Simplified from 5 phases to 3 implementation phases + finalization
- Categories are tech-based (already selected and downloaded to data/raw/)
- Data: Jan–Jun 2023, verified_purchase=true, grouped by parent_asin

[2026-03-25] - Plan Updated Per SI 507 v2 PDF
- CORRECTED date range: Jan 2023 - Jun 2023 (was 2022-2023)
- CONFIRMED categories: Electronics, Video Games, Software, Cell Phones and Accessories (exactly 4)
- CONFIRMED filtering: verified_purchase = True (document row count impact in Phase 1)
- Updated detailed plan: /Users/tylertran/.claude/plans/enchanted-weaving-honey.md

[2026-03-25] - Phase 1 Pipeline Implemented & Verified on Sample
- scripts/clean_data.py completed with full 10-step pipeline
- Verified on 100-record sample per JSONL file (sample run = 2.52M records output)
- Full dataset run deferred (43M+ records, ~5GB peak RAM expected)

[2026-03-26] - SI 507 v2 Docs Applied
- Updated METRICS.md with expansion formula, graph layer definitions
- docs/ directory organized: data_specs.md, METRICS.md, DECISIONS.md, phase1_data_integrity_report.md

[2026-03-27] - Codex Audit: 7 Critical Fixes Applied to clean_data.py
- Fixed date boundary (inclusive Jun 30), UTC timestamp handling, null validation, quality checks

[2026-03-27] - Phase 2 Scaffold Complete
- graph_logic/models.py: User, Category, Review, ReviewGraph classes
- graph_logic/analysis.py: retention + expansion pathway calculations
- tests/: test_models.py, test_analysis.py, test_integration.py, conftest.py
- 54/54 unit tests passing, 92% coverage
- Integration tests stubbed; activate after full CSV run

[2026-04-02] - ML Layer Added (ml/ package)
- New ml/ package: features.py, clustering.py, __init__.py
- User segmentation pipeline: MiniBatchKMeans (scales to 1.8M users); elbow + silhouette k selection with 200K subsampling; 6 cluster archetypes (One-and-done, Casual reviewer, Loyal returner, Power reviewer, Category explorer, Power explorer)
- Feature engineering: 12 global features per user for clustering
- Tests passing (test_ml_features.py, test_ml_clustering.py)
- Notebook cells appended for ML analysis and visualizations
- Fixed notebook datetime parsing bugs: format='ISO8601', timezone-aware date comparisons

[2026-04-16] - Retention prediction removed
- Removed ml/retention_model.py, tests/test_ml_retention.py, and retention feature functions from ml/features.py
- Web dashboard page renamed from "ML Insights" to "User Segmentation"; retention UI blocks removed
```

---

## Contact & Resources

**Student**: Tyler Tran
**Courses**: SI 511, SI 507
**University**: University of Michigan
**Project Root**: `/Users/tylertran/Documents/umich/courses/w26_project/`
**Data Location**: `data/raw/`
**Detailed Implementation Plan**: `/Users/tylertran/.claude/plans/lovely-shimmying-lecun.md`

For detailed implementation specifications and task breakdown, see the implementation plan file.
