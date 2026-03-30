# Data Specification & Documentation

**Phase 1 Analysis: Amazon Reviews Dataset**

This document describes the data sources, filtering pipeline, output schema, and quality metrics for the cleaned dataset used in retention and expansion pathway analysis.

---

## 1. Data Source

### Primary Source

**UCSD Amazon Reviews Dataset**
- **Provider**: UCSD AI Group
- **URL**: https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023
- **Format**: JSONL (JSON Lines) - one review per line
- **Download**: Pre-downloaded to `data/raw/` (project-relative path)

### Raw Data Files

| Category | Review File | Records | Size (observed on disk) |
|----------|-------------|---------|--------------------------|
| Electronics | Electronics.jsonl | 43.9M | ~21GB |
| Cell_Phones_and_Accessories | Cell_Phones_and_Accessories.jsonl | 20.8M | ~8.7GB |
| Video_Games | Video_Games.jsonl | 4.6M | ~2.5GB |
| Software | Software.jsonl | 4.9M | ~1.7GB |
| **Total (review files)** | — | **74.2M** | **~34GB** |

Note: `data/raw/` also includes metadata files; total directory size is ~43GB.

### Data Availability

Raw data spans: May 1996 - September 2023 (28 years of Amazon reviews)
- Note: Data heavily weighted toward 2010-2022 (older records appear first in files)
- Our analysis focuses on: January 1, 2023 - June 30, 2023 (6-month window)

---

## 2. Filtering Pipeline

### Overview

The cleaning pipeline applies filters in sequence to produce a final dataset of actual verified purchases within the target date range.

### Filter Sequence & Impact

**Filter 1: verified_purchase = True**
- **Rationale**: Ensures analysis uses only actual buyers, not just reviewers or deal hunters
- **Impact**: Removes unverified reviews (often spam, complaints, affiliate links)
- **Result**: Row counts are run-dependent (full run vs sample run). See `docs/data_quality_report.md` for current counts.
- **Note**: Proxy limitation - verified_purchase status is user self-reported, may not be 100% accurate

**Filter 2: Date Range (January 1, 2023 - June 30, 2023)**
- **Rationale**: 6-month observation window allows for 90-day retention measurement
- **Timezone**: UTC (explicit, for reproducibility across environments)
- **Boundary Logic**:
  - Start: 2023-01-01 00:00:00 UTC (inclusive)
  - End: 2023-06-30 23:59:59 UTC (inclusive)
  - Implemented as: `date >= 2023-01-01 AND date < 2023-07-01` (UTC)
- **Impact**: Row counts are run-dependent. Use the latest quality report as source of truth.
- **Note**: Most Amazon reviews predate 2023; narrow window is intentional per SI 507 requirements

**Filter 3: Category Subset (Exactly 4 Categories)**
- **Selected Categories** (per SI 507 v2 PDF):
  1. Electronics
  2. Video_Games
  3. Software
  4. Cell_Phones_and_Accessories
- **Rationale**: Tech categories chosen to avoid high-demand bias (per SI 507 guidance on category selection)
- **Impact**: Implicit in file selection; all 4 categories retained after date filtering
- **Note**: No reviews removed by this filter; only input file selection

**Filter 4: Group by parent_asin (Product Model Level)**
- **Rationale**: Deduplicates product variants (colors, sizes, editions) to product model level
- **Logic**:
  - `parent_asin` = product model (e.g., "iPhone case model X")
  - `asin` = specific variant (e.g., "iPhone case model X in red")
- **Impact**: Prevents inflating user counts when users review multiple variants of same product
- **Result**: 369,157 unique parent_asin across all reviews
- **Variant Ratio**: Average 2.3x variants per product model (e.g., 100 variants grouped to ~43 parent ASINs)

**Filter 5: Remove Duplicate (user_id, parent_asin, timestamp) Combinations**
- **Rationale**: Handles cases where same user submitted multiple reviews for same product at exact same timestamp (data entry error or system glitch)
- **Logic**:
  - Key = (user_id, parent_asin, timestamp)
  - Keep first occurrence, remove subsequent exact duplicates
  - **Important**: Multiple reviews on same day are preserved (different timestamps)
- **Impact**: Run-dependent. Check `docs/data_quality_report.md` for current counts
- **Note**: This is deduplication at exact timestamp level, NOT same-day level

### Final Output (Run-Dependent)

The checked-in cleaned dataset may be produced from either:
- a **full run** (`python3 scripts/clean_data.py`), or
- a **sample run** (`python3 scripts/clean_data.py --sample-size N`).

For current record counts, category coverage, and date range, use:
- `docs/data_quality_report.md` (authoritative)
- `wc -l data/cleaned/cleaned_reviews.csv` (quick row check)

---

## 3. Output Schema

### Column Definitions (12 Total)

| # | Column | Type | Description | Example |
|---|--------|------|-------------|---------|
| 1 | `user_id` | string | Unique user identifier (anonymized) | AEVPPTMG43C6GWSR7I2UGRQN7WFQ |
| 2 | `parent_asin` | string | Product model identifier (grouped variants) | B09TZQDTLQ |
| 3 | `asin` | string | Product variant identifier | B0BGHNQNPC |
| 4 | `timestamp` | int64 | Original millisecond Unix timestamp | 1673202172768 |
| 5 | `date` | datetime | Converted UTC datetime | 2023-01-08 18:22:52.768000+00:00 |
| 6 | `rating` | float | Review rating (1-5 scale) | 1.0, 5.0 |
| 7 | `verified_purchase` | bool | Verified purchase flag (always True in cleaned data) | True |
| 8 | `category_name` | string | Product category | Electronics, Video_Games, Software, Cell_Phones_and_Accessories |
| 9 | `helpful_vote` | int64 | Count of "helpful" votes from other users | 0, 5, 127 |
| 10 | `user_first_date` | datetime | User's first review date in this category (UTC) | 2023-01-08 18:22:52.768000+00:00 |
| 11 | `days_since_first` | int64 | Days elapsed from user's first review in category | 0, 15, 89 |
| 12 | `review_sequence` | int64 | Sequential review number for user in this category (1, 2, 3, ...) | 1, 2, 5 |

### Key Derived Columns

**`user_first_date`**
- Calculated per (user_id, category_name) pair
- Represents entry point into category
- Used to define 90-day retention window
- **Important**: Resets per category (user's first date in Electronics ≠ first date in Video_Games)

**`days_since_first`**
- Derived: (date - user_first_date).days
- Used for retention window filtering
- Range: run-dependent; not pre-filtered to <= 90 in cleaning (90-day logic is applied in metric calculations)
- Example: If first review Jan 5, review on Jan 15 = 10 days_since_first

**`review_sequence`**
- Incremental counter: 1, 2, 3, ... per (user_id, category_name)
- Used to identify multi-review users
- Retention requires: review_sequence >= 2

---

## 4. Data Quality Metrics

### Validation Checks (Run-Dependent)

Validation results are computed by the cleaning pipeline and written to `docs/data_quality_report.md`.
Do not treat hardcoded counts in this document as authoritative.

### Data Distribution (Run-Dependent)

Distribution statistics (users, ratings, helpful votes, review frequency) depend on whether the current artifact is a sample or full run.
Use notebook/script outputs tied to the current `cleaned_reviews.csv`.

---

## 5. Data Limitations & Assumptions

### Known Limitations

1. **Verified Purchase Proxy**
   - Flag is user self-reported and imperfect
   - Some fraudulent purchases may pass verification
   - Some legitimate purchases may lack verification

2. **Narrow Date Window**
   - Only 3.4% of all historical reviews fall in Jan-Jun 2023
   - Most early Amazon data (2010-2022) excluded from analysis
   - Results reflect only recent behavior patterns

3. **Category Grouping**
   - Product variants grouped at parent_asin level
   - Some parent ASINs may include slightly different products (e.g., editions of same book)
   - Analysis treats all variants equally

4. **User Anonymization**
   - user_id is anonymized but consistent within dataset
   - Cannot link reviews to real identities
   - Cross-dataset linking impossible

5. **Helpful Votes Timing**
   - Represent cumulative votes at data extraction time
   - Do not reflect vote progression over time
   - Biased toward older reviews (more time to accumulate votes)

6. **90-Day Retention Window**
   - Binary metric: either retained or not (no partial credit)
   - Single threshold (2+ reviews, 2+ days) may not capture all engagement
   - Doesn't measure review quality, only quantity and frequency

### Assumptions in Analysis

1. **User Independence**: Each user's behavior assumed independent of others
2. **Category Independence**: Retention/expansion metrics assume categories are discrete (users don't influence each other within categories)
3. **Timezone Consistency**: All times normalized to UTC; assumes timestamp accuracy in source data
4. **First-Category Semantics**: "First category" = the category of the user's chronologically earliest review across all 4 categories in the dataset
5. **90-Day Completion**: Users entering near the dataset end date (e.g., June 2023) do **not** have a fully observed 90-day follow-up window in this dataset and should be handled explicitly in Phase 2 logic.

---

## 6. Processing & Implementation

### Cleaning Script

**Location**: `scripts/clean_data.py`

**Key Features**:
- Handles large files (50M+ rows) with pandas
- Applies filters in deterministic order
- Derives retention columns efficiently
- Generates quality report with computed checks
- Supports `--sample-size N` for testing
- Supports `--output-dir` for custom output location

**Running Cleaning**:
```bash
# Full dataset (production)
python3 scripts/clean_data.py

# Sample run (testing, 100 records/file)
python3 scripts/clean_data.py --sample-size 100

# Custom output directory
python3 scripts/clean_data.py --output-dir /custom/path/data/cleaned
```

### Output Files

**Cleaned Data**:
- Location: `data/cleaned/cleaned_reviews.csv`
- Size: run-dependent (small for sample runs; ~348MB for the last known full run)
- Format: CSV with header row
- Encoding: UTF-8

**Quality Report**:
- Location: `docs/data_quality_report.md`
- Contents: Row counts at each filtering step, validation results
- Auto-generated with computed checks

---

## 7. Reproducibility

### Environment

- **Python**: 3.11+ (venv: `/venv/`)
- **Key Libraries**: pandas, numpy, datetime
- **OS**: macOS/Linux (Unix-based for path handling)

### Reproducibility Notes

1. **Timezone**: UTC explicitly enforced in code
   - Local timezone doesn't affect results
   - Same output on any machine at any time

2. **File Ordering**: Filters applied consistently
   - Verified_purchase → date range → category → deduplication → derivation
   - Same order ensures same results

3. **Pandas Determinism**:
   - drop_duplicates with keep='first' is deterministic
   - groupby().transform() preserves order within groups
   - Results reproducible across runs

4. **Floating-Point Precision**:
   - Date calculations use integer days (days_since_first)
   - No floating-point rounding errors

### Re-running Cleaning

To regenerate cleaned dataset from raw files:
```bash
source venv/bin/activate
python3 scripts/clean_data.py
# Output: data/cleaned/cleaned_reviews.csv + docs/data_quality_report.md
```

Expected output size/counts are run-dependent. Verify against `docs/data_quality_report.md`.

---

## 8. References

| Reference | Location | Purpose |
|-----------|----------|---------|
| SI 507 PDF | `docs/course_specs/SI 507.pdf` | Course requirements, metric definitions |
| Metrics Documentation | `docs/METRICS.md` | Retention & expansion formulas |
| Quality Report | `docs/data_quality_report.md` | Filtering statistics & validation results |
| Cleaning Script | `scripts/clean_data.py` | Implementation of filtering pipeline |
| CLAUDE.md | Project root | Technical guidance & constraints |
| Raw Data Source | `data/raw/` | Downloaded JSONL files (read-only) |

---

**Last Updated**: 2026-03-27
**Status**: Methodology/documentation updated; verify current run mode (sample vs full) before Phase 2
**Next Phase**: Graph logic implementation after confirming full-run artifact (if required)
