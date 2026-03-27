# CLAUDE.md - Project Guidelines & Architecture

**Project**: Amazon Reviews Analysis System (SI 511 Data Science + SI 507 Graph Logic)
**Deadline**: April 24, 2026 | Checkpoint: April 3, 2026
**Status**: Phase 1 pipeline complete (sample verified; full CSV run pending). Phase 2 ready to start.

---

## Quick Start

```bash
# Activate environment
source venv/bin/activate

# Run data cleaning
python3 scripts/clean_data.py

# Open notebook
jupyter notebook notebooks/CLEANED_DATA_EXPLORER.ipynb
```

---

## Project Structure

```
/
├── venv/                          # Python virtual environment (required)
├── data/
│   ├── raw/                       # Raw JSONL data files (DO NOT MODIFY)
│   │   ├── Cell_Phones_and_Accessories.jsonl
│   │   ├── Electronics.jsonl
│   │   ├── Software.jsonl
│   │   ├── Video_Games.jsonl
│   │   └── meta_*.jsonl           # (metadata files, not used in cleaning)
│   └── cleaned/
│       └── cleaned_reviews.csv    # OUTPUT: Combined cleaned data (all categories)
├── scripts/
│   └── clean_data.py              # Data cleaning pipeline
├── docs/
│   ├── DATA_QUALITY_REPORT.md     # Row counts at each filtering step
│   ├── DATA.md                    # Data spec & notes
│   ├── METRICS.md                 # Retention/expansion definitions
│   ├── PHASE_1_DATA_INTEGRITY_REPORT.md  # Validation audit report
│   └── course_specs/              # Course requirement PDFs
├── logs/                          # Session logs (one file per session)
│   ├── LOG_INDEX.md               # Master index, checkpoints, decisions
│   └── YYYY-MM-DD_sessionID_*.md  # Individual session logs
├── notebooks/
│   └── CLEANED_DATA_EXPLORER.ipynb  # Interactive data exploration & editing
├── graph_logic/                   # (Phase 2: to be created)
├── tests/                         # (Phase 2: to be created)
├── web/                           # (Phase 3: to be created)
├── PROJECT_PLAN.md                # High-level project overview
├── logs.md                        # Pointer to logs/LOG_INDEX.md
└── requirements.txt               # Python dependencies
```

---

## Data Specification (CRITICAL)

**Source**: UCSD Amazon reviews dataset (JSONL format)

**Filtering Pipeline** (in order):
1. ✅ `verified_purchase = True` only (94.8% retained in sample)
2. ✅ Date range: **January 1, 2023 - June 30, 2023** (4.2% retained after VP filter)
3. ✅ Categories: Exactly 4:
   - Electronics
   - Video Games
   - Software
   - Cell Phones and Accessories
4. ✅ Group by `parent_asin` (not individual ASIN)
5. ✅ Remove duplicate (user_id, parent_asin, timestamp) combinations

**Output Columns** (12 total, NO brand field):
- `user_id` - User identifier
- `parent_asin` - Product model identifier
- `asin` - Product variant
- `timestamp` - Original millisecond timestamp
- `date` - Converted datetime (UTC)
- `rating` - Review rating (1-5)
- `verified_purchase` - Boolean (always True)
- `category_name` - Product category
- `helpful_vote` - Count of helpful votes
- `user_first_date` - User's first review date in category (derived)
- `days_since_first` - Days elapsed from first review (derived)
- `review_sequence` - Review number in sequence (derived)

**Expected Scale**:
- 43M+ raw records across 4 categories
- ~4% pass date range filter (Jan-Jun 2023)
- Output: ~1-2M cleaned records (estimate)

---

## Cleaning Pipeline (scripts/clean_data.py)

**Run with defaults:**
```bash
python3 scripts/clean_data.py
```

**Run on sample (for testing):**
```bash
python3 scripts/clean_data.py --sample-size 25
```

**Pipeline Steps:**
1. Load JSONL file
2. Filter: verified_purchase = True
3. Filter: date range (Jan 2023 - Jun 2023)
4. Document variant grouping (parent_asin analysis)
5. Remove duplicate (user_id, parent_asin, timestamp) combinations
6. Derive retention columns
7. Validate nulls in critical fields
8. Combine all 4 categories
9. Export to CSV
10. Generate DATA_QUALITY_REPORT.md

**Output Files:**
- `data/cleaned/cleaned_reviews.csv` - Combined cleaned dataset
- `docs/DATA_QUALITY_REPORT.md` - Filtering statistics

---

## Key Rules & Decisions

### Data Architecture
- ✅ **One combined file** (not separate by category)
- Reason: Retention + expansion analysis are cross-categorical; Phase 2 graph needs all data combined

### Column Selection
- ✅ **NO brand field** in output
- Reason: Analysis focuses on category-level retention/expansion, not product characteristics

### Documentation
- All calculations must be transparent and traceable
- Include calculation examples in code comments
- Row counts documented at each filtering step
- Manual spot-checks required for retention calculations (5+ sample users)

### Testing
- Target: 80%+ code coverage
- Unit tests for all classes (Phase 2)
- Integration tests for pipeline
- Manual verification of 5+ sample users for retention math

### Token Efficiency
- Auto-updates every 5 minutes (not every 1 minute)
- Log only on significant changes (not every status check)
- Manual status checks available on-demand

---

## Phases Overview

### Phase 1: Data Cleaning (By April 3)
- ✅ Load & filter data (verified_purchase, date range, categories)
- ✅ Remove duplicates & derive columns
- ✅ Export cleaned CSV
- ✅ Generate quality report
- **Status**: Code complete. Sample run verified (100 records/file). Full dataset run pending.

### Phase 2: Graph Logic (April 4-10)
- Build OOP classes: User, Category, Review, Graph
- Implement retention calculations (2+ reviews on 2+ distinct days, within 90-day window)
- Identify high-retention categories (top quartile, min 30+ users)
- Analyze expansion pathways using conditional probability difference formula
- Construct two graph layers:
  - **User-Product Interaction Layer**: Nodes (users, products), Edges (reviews with timestamp, rating, category, brand)
  - **Product Transition Layer**: Nodes (categories), Edges (connected when same user reviews both over time)
- Write comprehensive tests (80%+ coverage)
- **Key File**: `graph_logic/models.py`, `graph_logic/analysis.py`

### Phase 3: Web Interface (April 11-17)
- Build Streamlit dashboard
- Implement 4+ interaction modes:
  1. View category rankings by retention rate
  2. Filter categories by metrics
  3. Explore expansion pathways
  4. Inspect category details
- **Key File**: `web/app.py`

### Phase 4: Finalization (April 18-24)
- Organize code & clean up
- Complete documentation (DATA.md, METRICS.md, README.md)
- Full test suite passing
- Performance optimization
- **Deadline**: April 24, 2026

---

## Retention & Expansion Definitions (for Phase 2)

**Retention (90-day window):**
- User is retained in a category if, within 90 days of their first review in that category, they leave **2 or more reviews on at least 2 distinct days** for products in the same category
- **Retention Rate** = Σ(users retained in category) / Σ(all users who reviewed in category)
- **High-Retention Category**: Product category whose retention rate falls in the **top quartile** of observed category retention rates, among categories with at least a minimum number of entering users

**Expansion Pathway (90-day window):**
- An entry category is considered a **strong expansion pathway** if users whose first reviewed category is A have an **above-baseline probability** of later reviewing a product in a different, high-retention category within 90 days
- **ExpansionDifference A→B** = P(B within 90d | first category = A) − P(B within 90d | first category ≠ A)
  - Where: A = entry category, B = destination category (B ≠ A, B is high-retention)
  - Positive difference indicates A leads to above-baseline expansion to B
  - Baseline = probability of entering high-retention category B for users whose first entry was NOT in A

---

## Important Notes

1. **Data Heavily Weighted to 2010-2022**
   - First 25 records from each file are mostly old
   - Date range filter (Jan-Jun 2023) is very restrictive (4.2% pass)
   - This is normal; full file processing needed

2. **Memory Management**
   - Start with Pandas; switch to Polars/DuckDB if hitting RAM limits
   - Current test: 43M records + filtering uses ~5GB peak

3. **Retention Pool Size**
   - Print absolute retained counts early in Phase 1
   - If retained users < 5% of total, flag for threshold adjustment
   - May need to extend window to 180 days or relax constraints

4. **Manual Verification Required**
   - Spot-check 5+ sample users for retention calculations
   - Example: User X, first review in Video_Games 2023-01-05
   - Find all reviews within [2023-01-05, 2023-04-05], count distinct days

5. **Virtual Environment**
   - REQUIRED for project
   - Contains: pandas, numpy, jupyter, networkx, polars, sklearn, torch, etc.
   - Activate: `source venv/bin/activate`

---

## Logging & Progress

**Log Structure:**
- `logs/LOG_INDEX.md` — Master index with session list, checkpoints, decisions
- `logs/YYYY-MM-DD_sessionID_short-description.md` — One file per session
- `docs/DATA_QUALITY_REPORT.md` — Detailed filtering stats
- `notebooks/CLEANED_DATA_EXPLORER.ipynb` — Interactive data exploration

**Reading Logs (token-efficient):**
- Start with `logs/LOG_INDEX.md` for overview and current status
- Only read individual session files when you need details about a specific session
- Do NOT read all session files at once

**View latest status:**
- Check "Current Status" section in `logs/LOG_INDEX.md`
- Check `docs/DATA_QUALITY_REPORT.md` for data pipeline results

---

## Success Criteria

- [x] Data correctly filtered (verified_purchase=True, Jan-Jun 2023, 4 categories) — pipeline verified on sample; full run pending
- [ ] Retention calculations manually verified (5+ sample users) — Phase 2
- [ ] Graph structure validates user-category relationships — Phase 2
- [ ] Expansion pathways accurate (90-day windows, baseline comparison) — Phase 2
- [ ] Web interface intuitive (4+ interaction modes) — Phase 3
- [ ] OOP design with User, Category, Review, Graph classes — Phase 2
- [ ] 80%+ test coverage — Phase 2
- [ ] Complete documentation (DATA.md, METRICS.md, README) — Phase 4

---

## For Future Claude Sessions

**Start Here:**
1. Check `PROJECT_PLAN.md` for high-level overview
2. Read `logs/LOG_INDEX.md` for session history and current status
3. Check `docs/DATA_QUALITY_REPORT.md` if Phase 1 complete
4. Review this CLAUDE.md for rules & structure

**Before Running Scripts:**
- Activate venv: `source venv/bin/activate`
- Check project structure matches above

**Key Commands:**
- Data cleaning: `python3 scripts/clean_data.py`
- Explore data: `jupyter notebook notebooks/CLEANED_DATA_EXPLORER.ipynb`
- Check status: Manual checks as needed (every 5 min auto-updates)

## Critical Constraints (Lifetime)

### Session Logging Guidelines

**Location**: `logs/` directory. One markdown file per session.

**File naming**: `YYYY-MM-DD_sessionID_short-description.md`
- Examples: `2026-03-25_session1_plan-revision-phase1.md`, `2026-04-04_session5_graph-logic.md`
- Use lowercase with hyphens for the description
- If multiple sessions on same date, use suffixes: `session3`, `session3b`, `session3c`

**Each session file must include:**
```markdown
# Session N: Brief Description

**Date**: YYYY-MM-DD ~HH:MM TZ
**Model**: Model name used

---

## User Requests
- What Tyler asked for

## Completed
- Item 1
- Item 2

## Blockers / Notes
- Note 1

## Next Steps
1. Step 1
```

**After creating a session file:**
1. Add a row to the session table in `logs/LOG_INDEX.md`
2. Update the "Current Status" section in `logs/LOG_INDEX.md`

**Key rules:**
- Log every significant session
- Log only on significant changes (skip redundant entries)
- Do NOT put all sessions in a single file (defeats token efficiency)
- Keep session files concise — details belong in code comments and docs, not logs

---

## Critical Constraints (Phase 1 - Data Cleaning)

**Data Filtering (mandatory order):**
- Date range: MUST be Jan 1, 2023 - Jun 30, 2023
- verified_purchase: MUST be True only
- Categories: EXACTLY 4 (no more, no less)
- Grouping: MUST be by parent_asin, not asin
- Deduplication: MUST remove duplicate (user_id, parent_asin, timestamp) combinations

**Output:**
- One file: Combined CSV (not separate by category)
- Location: `data/cleaned/cleaned_reviews.csv`
- No brand field in output columns

---

**Last Updated**: 2026-03-27
**Status**: Phase 1 pipeline code complete. Full dataset CSV needs regeneration before Phase 2.
