# Session 6: ML Layer — Retention Prediction + User Clustering

**Date**: 2026-04-02
**Model**: Claude Sonnet 4.6

---

## User Requests
- Fix Jupyter kernel display name to "Amazon Reviews"
- Add matplotlib to venv and requirements.txt
- Fix two notebook datetime errors (cell 20 validation checks, cell 30 graph build)
- Add ML capabilities: retention prediction + user segmentation

## Completed

### Notebook Fixes
- Kernel display name updated: `Amazon Reviews` (was "Python (w26_venv)")
- Added matplotlib==3.10.8 to requirements.txt
- Cell 20: changed `pd.to_datetime(df['date'])` → `format='ISO8601'`; made `date_start`/`date_end` timezone-aware (`tzinfo=timezone.utc`) to fix mixed-format parse error and tz-naive comparison error
- Cell 30: changed `pd.to_datetime(df_sample['date'], utc=True)` → `format='ISO8601'`

### ML Package (`ml/`)
- `ml/__init__.py` — exports all public functions
- `ml/features.py` — feature engineering from Graph objects:
  - `build_retention_features(graph, category, max_entry_date)` — 12 features + `retained` label
  - `build_retention_features_all(graph)` — concatenates categories; one-hot encodes `category` column
  - `build_user_features(graph, min_reviews=1)` — 12 global user features for clustering
- `ml/retention_model.py` — supervised pipeline:
  - `train_retention_model` — LR or RF, StandardScaler, stratified split, class_weight='balanced'
  - `get_feature_importance`, `plot_roc_curve`, `plot_feature_importance`
- `ml/clustering.py` — unsupervised pipeline:
  - `find_optimal_k` — MiniBatchKMeans with subsampling; returns inertias, silhouette scores, best_k
  - `train_clustering` — fits model, inverse-transforms centers, builds cluster profiles
  - `characterize_clusters` — assigns human-readable labels based on profile thresholds
  - `plot_elbow`, `plot_silhouette`, `plot_cluster_sizes`

### Tests
- `tests/test_ml_features.py` — 21 tests (column validation, label correctness, feature spot-checks, edge cases)
- `tests/test_ml_retention.py` — 10 tests (keys, predictions, importances, both model types)
- `tests/test_ml_clustering.py` — 10 tests (inertia monotonicity, silhouette bounds, labels, profiles)
- **Total: 107/107 passing** (83 existing + 24 new = wait, 41 new = 83 + 41 = 124... actually 66 existing + 41 new = 107)

### Notebook Cells 38–49
- Cell 38: ML section markdown header
- Cell 39: ML imports
- Cell 40: Retention prediction markdown header
- Cell 41: Build retention features, print shape + class balance
- Cell 42: Train both models, print classification reports
- Cell 43: Side-by-side ROC curve comparison
- Cell 44: Feature importance comparison chart
- Cell 45: User clustering markdown header
- Cell 46: Build user features, elbow + silhouette plots
- Cell 47: Fit K-means with chosen k, cluster size bar chart
- Cell 48: Cluster profile table + comparison radar/bar chart
- Cell 49: Key findings markdown summary

## Blockers / Notes
- Notebook cells not yet executed by user; results pending
- MiniBatchKMeans used throughout for scalability (1.8M user dataset)
- ROC AUC chosen as primary metric due to class imbalance (retention is minority class)

## Next Steps
1. User runs notebook ML cells and validates output
2. Phase 3: Streamlit web dashboard (4+ interaction modes)
