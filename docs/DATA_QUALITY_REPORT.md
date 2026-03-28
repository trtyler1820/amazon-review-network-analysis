# Data Quality Report
Generated: 2026-03-28 07:10:40 UTC
Sample Size: Full dataset

## Summary
- Total records loaded: 74204685
- Total records after cleaning: 2523881
- Unique categories: 4
- Unique users: 1832347
- Unique products (parent_asin): 369782
- Date range: 2023-01-01 00:00:00.581000+00:00 to 2023-06-30 23:59:37.742000+00:00

## Filtering Impact by Category

### Cell_Phones_and_Accessories
- Raw count: 20812945
- After verified_purchase filter: 19726191 (94.8% retained)
- After date filter (2023-01-01 to 2023-06-30): 824482 (4.2% retained)
- After deduplication: 812853 (98.6% retained)
- Variant analysis: 219094 ASINs → 120031 parent ASINs (ratio: 1.83x)
- **Final count: 812853**

### Electronics
- Raw count: 43886944
- After verified_purchase filter: 40546884 (92.4% retained)
- After date filter (2023-01-01 to 2023-06-30): 1561830 (3.9% retained)
- After deduplication: 1540147 (98.6% retained)
- Variant analysis: 311917 ASINs → 220546 parent ASINs (ratio: 1.41x)
- **Final count: 1540147**

### Software
- Raw count: 4880181
- After verified_purchase filter: 4645281 (95.2% retained)
- After date filter (2023-01-01 to 2023-06-30): 28137 (0.6% retained)
- After deduplication: 27760 (98.7% retained)
- Variant analysis: 5296 ASINs → 5114 parent ASINs (ratio: 1.04x)
- **Final count: 27760**

### Video_Games
- Raw count: 4624615
- After verified_purchase filter: 3982807 (86.1% retained)
- After date filter (2023-01-01 to 2023-06-30): 145336 (3.6% retained)
- After deduplication: 143121 (98.5% retained)
- Variant analysis: 33000 ASINs → 24091 parent ASINs (ratio: 1.37x)
- **Final count: 143121**

## Data Quality Checks (Computed)
- All records have user_id (no nulls): ✓
- All records have parent_asin (no nulls): ✓
- All records have timestamp (no nulls): ✓
- All records have verified_purchase = True: ✓
- All records have category_name (no nulls): ✓
- All records have valid rating [1-5] (no nulls): ✓
- Date range check: 2023-01-01 to 2023-06-30 [within 2023-01-01 to 2023-06-30]: ✓

## Retention Analysis Readiness
- Minimum users per category: 23157
- Average days per user: 3.0
- Review sequence column derived ✓
- user_first_date calculated ✓
