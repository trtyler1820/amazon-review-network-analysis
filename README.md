# Amazon Reviews Analysis: User Retention & Expansion Patterns

Amazon review data offers a public record of user engagement with products over time. By treating reviews as a proxy for product interaction, this project analyzes which product categories are strong entry points for users, which categories are associated with repeat engagement, and which early product paths lead users into broader downstream category exploration.

## Objective

Using a subset of the [UCSD Amazon reviews dataset](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023), I built a temporal user-product interaction model to analyze which product categories are strongest at retaining user engagement and which entry categories are most associated with later expansion into other high-value categories. The goal is to frame the analysis as an exploration of the data to support product growth opportunities.

## Business / Product Questions

- Which product categories appear to be the highest-value candidates for further strategic investment?
- Which product categories are the strongest user entry points?
- Which categories attract many first-time reviewers, but fail to retain them?
- Which first reviewed categories are most associated with later expansion into high-retention categories?

---

## Quick Start

### Prerequisites
- Python 3.11+
- macOS/Linux (Unix-based system)
- ~8GB RAM recommended for data processing
- ~50GB disk space recommended for raw data, metadata, and cleaned outputs

### Installation

1. **Clone/navigate to project:**
```bash
cd /Users/tylertran/Documents/umich/courses/w26_project
```

2. **Activate virtual environment:**
```bash
source venv/bin/activate
```

3. **Verify dependencies** (already installed):
```bash
pip list | grep -E "pandas|numpy|jupyter|networkx|pytest"
```

### Run Data Cleaning

```bash
# Full dataset (production)
python3 scripts/clean_data.py

# Sample run (testing, 100 records/file)
python3 scripts/clean_data.py --sample-size 100

# Custom output directory
python3 scripts/clean_data.py --output-dir /custom/path/data/cleaned
```

### Explore Cleaned Data

```bash
jupyter notebook notebooks/CLEANED_DATA_EXPLORER.ipynb
```

---

## Project Structure

```
/
├── venv/                          # Python virtual environment
├── data/raw/                      # Raw JSONL data files (DO NOT MODIFY)
│   ├── Cell_Phones_and_Accessories.jsonl
│   ├── Electronics.jsonl
│   ├── Software.jsonl
│   ├── Video_Games.jsonl
│   └── meta_*.jsonl               # Metadata (not used)
├── scripts/
│   └── clean_data.py              # Data cleaning pipeline
├── data/
│   └── cleaned/
│       ├── cleaned_reviews.csv    # OUTPUT: Combined cleaned data
│       └── cleaned_reviews.parquet # (if pyarrow installed)
├── graph_logic/                   # Phase 2: planned (may not exist yet)
├── web/                           # Phase 3: planned (may not exist yet)
├── tests/                         # Planned test suite (may not exist yet)
├── docs/
│   ├── DATA.md                    # Data spec & filtering pipeline
│   ├── METRICS.md                 # Retention & expansion definitions
│   ├── DATA_QUALITY_REPORT.md     # Filtering statistics
│   └── PHASE_1_VALIDATION_REPORT.md # Audit & fixes
├── PROJECT_PLAN.md                # High-level overview
├── CLAUDE.md                      # Technical guidance & architecture
├── notebooks/
│   └── CLEANED_DATA_EXPLORER.ipynb  # Interactive data exploration
├── logs.md                        # Session progress log
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

---

## Key Files & Documentation

### Getting Started
- **This file** (`README.md`) - Start here
- `PROJECT_PLAN.md` - High-level project overview & deadlines
- `CLAUDE.md` - Technical constraints & implementation guidance

### Data & Metrics
- `docs/DATA.md` - Data spec, filtering pipeline, schema, quality metrics
- `docs/METRICS.md` - Retention & expansion formula definitions
- `docs/DATA_QUALITY_REPORT.md` - Auto-generated filtering statistics

### Implementation
- `scripts/clean_data.py` - Data cleaning pipeline (Phase 1)
- `graph_logic/` - Graph logic implementation (Phase 2, TBD)
- `web/app.py` - Streamlit dashboard (Phase 3, TBD)
- `tests/` - Test suite (Phase 2-3)

### Progress & Audit
- `logs.md` - Session-by-session progress tracker
- `docs/PHASE_1_VALIDATION_REPORT.md` - Code audit & quality findings

---

## Data Specification

### Source
**UCSD Amazon Reviews Dataset**
- 74.2M raw reviews across 4 tech categories
- Date range: May 1996 - September 2023 (raw)
- Analysis window: January 1, 2023 - June 30, 2023

### Filtering Pipeline
1. `verified_purchase = True` → 95% retained
2. Date range (Jan-Jun 2023) → 3.5% retained
3. Categories: Electronics, Video_Games, Software, Cell_Phones_and_Accessories
4. Group by `parent_asin` (dedup variants)
5. Remove duplicate (user_id, parent_asin, timestamp) combinations

### Output
- **Records/Users/Products/Categories**: run-dependent (sample vs full)
- See `docs/DATA_QUALITY_REPORT.md` for current authoritative counts

### Schema (12 columns)
```
user_id, parent_asin, asin, timestamp, date, rating,
verified_purchase, category_name, helpful_vote,
user_first_date, days_since_first, review_sequence
```

See `docs/DATA.md` for complete schema documentation.

---

## Core Metrics

### Retention (90-Day Window)
A user is **retained** in a category if, within 90 days of their first review, they post **2+ reviews on 2+ distinct days**.

```
retention_rate(category) = retained_users / total_users
```

### Expansion Pathway (90-Day Window)
An entry category is a **strong expansion pathway** to a high-retention category if:

```
ExpansionDifference(A → B) = P(B | first = A) − P(B | first ≠ A) > 5%
```

Where P(B | first = A) = probability of reviewing category B within 90 days of entering via category A.

### High-Retention Categories
Categories in the **top quartile** of retention rates (with 30+ entering users).

See `docs/METRICS.md` for complete definitions, formulas, and worked examples.

---

## Project Phases

### ✅ Phase 1: Data Cleaning (By April 3, 2026)
**Status**: Pipeline complete; verify whether checked-in output is sample or full run

- ✅ Cleaning script and methodology implemented
- ✅ Quality report generation implemented
- ✅ Validation reports documented
- ⚠️ Current `cleaned_reviews.csv` may reflect a sample run depending on last execution

---

### 🔄 Phase 2: Graph Logic & Testing (April 4-10, 2026)
**Status**: Ready to Start

**Objectives**:
- [ ] Design OOP classes (User, Category, Review, Graph)
- [ ] Implement retention calculation engine
- [ ] Identify high-retention categories
- [ ] Analyze expansion pathways
- [ ] Write comprehensive tests (80%+ coverage)

**Deliverables**:
- `graph_logic/models.py` - Core classes
- `graph_logic/analysis.py` - Calculations
- `tests/` - Unit & integration tests
- Summary report (retention rates, expansion patterns)

**Key Metrics to Calculate**:
- Per-category retention rates
- High-retention category set (top quartile, 30+ users min)
- Expansion pathways (all category pairs A → B)

---

### 🎨 Phase 3: Web Interface (April 11-17, 2026)
**Status**: Ready After Phase 2

**Objectives**:
- [ ] Build Streamlit dashboard
- [ ] Implement category explorer
- [ ] Visualize expansion pathways
- [ ] Add filtering/sorting controls

**Deliverables**:
- `web/app.py` - Streamlit app
- Visualizations (retention charts, network graph, Sankey)

**Required Interactions** (4+):
1. View category rankings by retention rate
2. Filter categories by metrics
3. Explore expansion pathways
4. Inspect category details

---

### 📦 Phase 4: Finalization (April 18-24, 2026)
**Status**: After Phases 2 & 3

**Objectives**:
- [ ] Organize code & clean up
- [ ] Complete documentation
- [ ] Full test suite passing
- [ ] Performance optimization
- [ ] Final code review

---

## Key Commands

### Data Processing
```bash
# Run full cleaning
python3 scripts/clean_data.py

# Run with sample (100 records/file)
python3 scripts/clean_data.py --sample-size 100

# Verify output
head -1 data/cleaned/cleaned_reviews.csv
wc -l data/cleaned/cleaned_reviews.csv
```

### Exploration
```bash
# Open notebook
jupyter notebook notebooks/CLEANED_DATA_EXPLORER.ipynb

# Check data quality
cat docs/DATA_QUALITY_REPORT.md
```

### Testing (Phase 2+)
```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_models.py -v

# Coverage report
pytest --cov=graph_logic tests/
```

### Web Interface (Phase 3+)
```bash
# Run Streamlit app
streamlit run web/app.py
```

---

## Important Notes

### Data & Environment
- **Timezone**: All dates normalized to UTC for reproducibility
- **Memory**: Full cleaning uses ~5GB peak RAM (manageable on modern systems)
- **File Size**: cleaned CSV size is run-dependent (sample: tiny; full run: hundreds of MB)
- **Raw Data**: JSONL files in `data/raw/` are read-only

### Development
- **Virtual Environment Required**: Always activate `venv/` before running
- **Python Path**: Scripts assume project root as working directory
- **Dependencies**: Listed in `requirements.txt` (already installed in venv)

### Phase 2 Prerequisites
- Phase 1 cleaning must be complete (run `python3 scripts/clean_data.py` first)
- Read `docs/METRICS.md` thoroughly before implementing graph logic
- Study edge cases in `docs/DATA.md` (single-review users, timezone boundaries, etc.)

---

## Troubleshooting

### Memory Usage Too High
```bash
# Kill stale Jupyter kernels
pkill -9 -f "ipykernel_launcher"
```

### Data Not Loading
```bash
# Verify cleaned data exists
ls -lh data/cleaned/cleaned_reviews.csv

# Re-run cleaning
python3 scripts/clean_data.py --sample-size 25
```

### Tests Failing
```bash
# Check pytest is installed
pip install pytest pytest-cov

# Run with verbose output
pytest tests/ -v --tb=short
```

### Script Permission Issues
```bash
# Make script executable
chmod +x scripts/clean_data.py

# Run explicitly
python3 scripts/clean_data.py
```

---

## Resources

### Documentation
- **Project Overview**: `PROJECT_PLAN.md`
- **Data Spec**: `docs/DATA.md`
- **Metrics**: `docs/METRICS.md`
- **Technical Guidance**: `CLAUDE.md`
- **Progress Log**: `logs.md`

### Data

> **Note**: Raw and cleaned data files are not tracked in git (too large). Download the raw data and regenerate the cleaned dataset locally.

**Download raw data** (requires `huggingface_hub`):
```bash
pip install huggingface_hub
python3 -c "
from huggingface_hub import hf_hub_download
import os
os.makedirs('data/raw', exist_ok=True)
for cat in ['Electronics', 'Video_Games', 'Software', 'Cell_Phones_and_Accessories']:
    hf_hub_download(repo_id='McAuley-Lab/Amazon-Reviews-2023',
                    filename=f'raw_review_{cat}.jsonl',
                    repo_type='dataset', local_dir='data/raw')
"
```

**Regenerate cleaned data**:
```bash
python3 scripts/clean_data.py
```

- **Source**: https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023
- **Quality Report**: `docs/DATA_QUALITY_REPORT.md` (auto-generated by cleaning script)

### Courses
- **SI 511**: Data Science - Focus on data cleaning & web interface
- **SI 507**: Graph Logic - Focus on graph structure & retention/expansion analysis
- **SI 507 PDF**: `docs/course_specs/SI 507.pdf`

---

## Contact & Support

**Student**: Tyler Tran
**Courses**: SI 511, SI 507
**University**: University of Michigan
**Project Root**: `/Users/tylertran/Documents/umich/courses/w26_project/`

For questions or feedback:
- Check `logs.md` for session history
- Review `CLAUDE.md` for technical constraints
- Consult `docs/METRICS.md` for metric definitions

---

## Success Criteria

- [ ] Data correctly filtered (verified_purchase=True, Jan-Jun 2023, 4 categories)
- [ ] Retention calculations manually verified on 5+ sample users
- [ ] Graph structure correctly represents user-category relationships
- [ ] Expansion pathway analysis accurate (90-day windows, baseline comparison)
- [ ] Web interface intuitive with 4+ interaction modes
- [ ] OOP design with User, Category, Review, Graph classes
- [ ] 80%+ test coverage with passing unit/integration tests
- [ ] Complete documentation (DATA.md, METRICS.md, README.md)

---

**Status**: Ready for Phase 2 once full-run data state is confirmed (if required)
**Next Step**: Implement Phase 2 graph logic and compute retention/expansion from current verified artifact
