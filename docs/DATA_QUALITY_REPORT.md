# Data Quality Report
Generated: 2026-03-27 22:12:58 UTC
Sample Size: 100

## Summary
- Total records loaded: 400
- Total records after cleaning: 6
- Unique categories: 3
- Unique users: 6
- Unique products (parent_asin): 6
- Date range: 2023-01-08 18:22:52.768000+00:00 to 2023-03-03 12:11:57.223000+00:00

## Filtering Impact by Category

### Cell_Phones_and_Accessories
- Raw count: 100
- After verified_purchase filter: 97 (97.0% retained)
- After date filter (2023-01-01 to 2023-06-30): 4 (4.1% retained)
- After deduplication: 4 (100.0% retained)
- Variant analysis: 4 ASINs → 4 parent ASINs (ratio: 1.00x)
- **Final count: 4**

### Electronics
- Raw count: 100
- After verified_purchase filter: 97 (97.0% retained)
- After date filter (2023-01-01 to 2023-06-30): 1 (1.0% retained)
- After deduplication: 1 (100.0% retained)
- Variant analysis: 1 ASINs → 1 parent ASINs (ratio: 1.00x)
- **Final count: 1**

### Software
- Raw count: 100
- After verified_purchase filter: 93 (93.0% retained)
- After date filter (2023-01-01 to 2023-06-30): 0 (0.0% retained)
- After deduplication: 0 (0.0% retained)
- Variant analysis: 0 ASINs → 0 parent ASINs (ratio: 1.00x)
- **Final count: 0**

### Video_Games
- Raw count: 100
- After verified_purchase filter: 81 (81.0% retained)
- After date filter (2023-01-01 to 2023-06-30): 1 (1.2% retained)
- After deduplication: 1 (100.0% retained)
- Variant analysis: 1 ASINs → 1 parent ASINs (ratio: 1.00x)
- **Final count: 1**

## Data Quality Checks (Computed)
- All records have user_id (no nulls): ✓
- All records have parent_asin (no nulls): ✓
- All records have timestamp (no nulls): ✓
- All records have verified_purchase = True: ✓
- All records have category_name (no nulls): ✓
- All records have valid rating [1-5] (no nulls): ✓
- Date range check: 2023-01-08 to 2023-03-03 [within 2023-01-01 to 2023-06-30]: ✓

## Retention Analysis Readiness
- Minimum users per category: 1
- Average days per user: 0.0
- Review sequence column derived ✓
- user_first_date calculated ✓
