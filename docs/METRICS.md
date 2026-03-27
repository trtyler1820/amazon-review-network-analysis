# Project Metrics & Definitions

**Phase 1 Analysis: Amazon Reviews Retention and Cross-Category Expansion**

This document defines the core metrics used to analyze user retention and expansion patterns in Amazon review data. All calculations are based on the cleaned dataset: January 1, 2023 - June 30, 2023, verified_purchase = True, grouped by parent_asin.

---

## 1. Retention Metric (90-Day Window)

### Definition

A user is **retained** in a product category if:
- Within 90 days of their first review in that category, they post **2 or more reviews on at least 2 distinct days**

### Formula

```
first_ts(U, C) = min(timestamp) for user U in category C

reviews_90d(U, C) =
  { r | user_id(r)=U AND category(r)=C AND first_ts(U,C) <= ts(r) <= first_ts(U,C) + 90 days }

n_reviews_90d(U, C) = |reviews_90d(U, C)|
n_days_90d(U, C) = number of distinct calendar dates in reviews_90d(U, C)

is_retained(U, C) = 1 if n_reviews_90d(U, C) >= 2 AND n_days_90d(U, C) >= 2 else 0

retention_rate(C) =
  SUM(is_retained(U, C)) / COUNT(users with at least one review in C)
```

### Calculation Steps

1. **Identify entry point**: Find user's first review date in category C
   - Example: User A's first review in Electronics: 2023-01-05

2. **Define retention window**: All reviews within 90 days of first review
   - Window: [2023-01-05, 2023-04-05]

3. **Count distinct review days**: How many separate days user reviewed in category
   - Example: User A reviewed on [2023-01-05, 2023-01-15, 2023-01-15, 2023-02-10]
   - Distinct days: 3 (Jan 5, Jan 15, Feb 10)

4. **Check retention criteria**: 2+ reviews on 2+ distinct days?
   - User A: 4 reviews on 3 distinct days → ✓ **RETAINED**

5. **Aggregate**: Count all retained users per category
   - Electronics: 150 retained users / 1000 total users = **15% retention rate**

### Key Notes

- **Per-category semantics**: Retention is calculated independently for each category
  - User A might be retained in Electronics but not in Video Games
  - User first_date resets for each category

- **Same-day reviews count as 1 distinct day**: Multiple reviews on the same calendar day count as one "distinct day"
  - Example: [2023-01-05 10:00, 2023-01-05 14:00] = 1 distinct day (both same day)

- **90-day window is strict**: Use exact timestamps, inclusive of the endpoint
  - Include reviews where `ts(review) <= first_ts + 90*24h`
  - Do not rely only on integer `days_since_first` if strict boundary is required

- **UTC timezone**: All timestamps normalized to UTC for reproducibility

- **Tie handling**: If a user has identical earliest timestamps in multiple categories, mark as `first_category = TIE` and exclude from A-vs-not-A pathway denominators (or define an explicit deterministic tie-break rule).

---

## 2. Expansion Pathway Metric (90-Day Window)

### Definition

An entry category is a **strong expansion pathway** to another category if users whose first reviewed category is A have an **above-baseline probability** of later reviewing products in a high-retention category B within 90 days.

### Formula

```
P(B within 90d | first category = A) =
  COUNT(users where first_category = A AND reviewed_B within 90d of first_category_entry)
  / COUNT(users where first_category = A)

P(B within 90d | first category ≠ A) =
  COUNT(users where first_category ≠ A AND reviewed_B within 90d of first_category_entry)
  / COUNT(users where first_category ≠ A)

ExpansionDifference(A → B) =
  P(B within 90d | first = A) − P(B within 90d | first ≠ A)
```

Where:
- **A** = entry category (user's first reviewed category)
- **B** = destination category (must be high-retention category)
- **Baseline** = P(B within 90d | first ≠ A) = probability for users NOT entering via A
- **Positive ExpansionDifference** = strong pathway (A leads to above-baseline B engagement)

### Calculation Steps

**Example: Is Electronics (A) a strong pathway to Video Games (B)?**

Assume:
- Video Games is high-retention (top quartile)
- We want to know if entering via Electronics predicts Video Games expansion

**Step 1: Find users entering via Electronics**
- Users whose first review ever (across all categories) was in Electronics
- Example: 500 such users

**Step 2: Count Electronics→Video Games expansion (90d window)**
- Of those 500 users, how many reviewed Video Games within 90 days of their first Electronics review?
- Example: 120 users

```
P(Video_Games within 90d | first = Electronics) = 120 / 500 = 24%
```

**Step 3: Find baseline (users NOT entering via Electronics)**
- All other users (whose first category was NOT Electronics)
- Example: 3000 users

**Step 4: Count baseline Video Games expansion (90d window)**
- Of those 3000 non-Electronics users, how many reviewed Video Games within 90 days of their first-ever review?
- Example: 450 users

```
P(Video_Games within 90d | first ≠ Electronics) = 450 / 3000 = 15%
```

**Step 5: Calculate expansion difference**

```
ExpansionDifference(Electronics → Video_Games) = 24% − 15% = 9%
```

**Interpretation:**
- **+9% positive difference** = Electronics is a **strong expansion pathway to Video Games**
- Users entering via Electronics are 9 percentage points MORE likely to explore Video Games than the average user
- This indicates Electronics → Video Games is a meaningful customer journey pattern

### Categorization

**Expansion Strength (recommended):**
- **Strong pathway**: ExpansionDifference > 0, both cohorts meet minimum size (e.g., >= 100 users), and statistical uncertainty check (e.g., CI lower bound > 0)
- **Exploratory positive**: ExpansionDifference > +5% but fails one robustness criterion
- **Neutral/Negative**: ExpansionDifference <= 0 (or not robust)

---

## 3. High-Retention Categories

### Definition

A category is classified as **high-retention** if:
- Its retention rate falls in the **top quartile** of all observed category retention rates
- AND it has at least a **minimum threshold of entering users** (e.g., 30+)

### Calculation

1. **Calculate retention rate for all categories**
   - Example rates: Electronics (18%), Video_Games (12%), Software (8%), Cell_Phones (22%)

2. **Identify top quartile cutoff**
   - Compute the 75th percentile of category retention rates.
   - Classify categories with retention_rate >= Q75 as high-retention, then apply minimum-user threshold.
   - If category count is small (e.g., 4 categories), document tie behavior explicitly.

3. **Apply minimum user threshold**
   - Filter out categories with < 30 entering users
   - Example: If Software only has 15 entering users, exclude it from high-retention pool

4. **Result**: High-retention categories used for expansion pathway analysis
   - These become the destination categories (B) in expansion formulas

### Example

| Category | Retention Rate | Entering Users | High-Retention? |
|----------|----------------|----------------|-----------------|
| Cell_Phones | 22% | 150 | ✓ Yes (top quartile, 150 > 30) |
| Electronics | 18% | 200 | ✓ Yes (top quartile, 200 > 30) |
| Video_Games | 12% | 80 | ✗ No (below top quartile) |
| Software | 8% | 15 | ✗ No (below threshold, 15 < 30) |

**High-retention pool:** {Cell_Phones, Electronics}

---

## 4. Worked Example: Full Analysis (Conceptual)

### Setup

**Cleaned dataset:**
- Date range: Jan 1, 2023 - Jun 30, 2023
- Categories: Electronics, Video_Games, Software, Cell_Phones_and_Accessories
- Total scope: 1.8M+ users, 2.5M+ reviews

*Note: Real numerical results will be populated in Phase 2 after running actual retention and expansion calculations on the cleaned dataset.*

### Retention Analysis (Process)

**Step 1: Calculate per-category retention rates**

For each category, count:
- Total users who reviewed in that category
- Users retained (2+ reviews on 2+ distinct days within 90d of first review)
- Retention rate = retained / total per category

Result: Ordered list of retention rates by category.

**Step 2: Identify high-retention categories (top quartile + min 30 users)**

From the retention rates:
- Determine 75th percentile cutoff
- Filter categories with ≥ 30 entering users
- Result: Set of high-retention categories (destination categories for expansion analysis)

### Expansion Pathway Analysis (Process)

**Question: Which entry categories drive strong expansion to high-retention categories?**

**For each category pair (A → B where B is high-retention):**

1. Find users whose first category = A
2. Count how many reviewed B within 90 days of their first-category entry
3. Calculate P(B | first = A)

4. Find all users whose first category ≠ A
5. Count how many reviewed B within 90 days of their first-category entry
6. Calculate P(B | first ≠ A) — this is the baseline

7. Calculate ExpansionDifference(A → B) = P(B | first = A) − P(B | first ≠ A)

**Interpretation:**
- **Positive difference** (+5% or more) = A is a strong pathway to B
- **Neutral/Negative difference** (≤ +5%) = Not a strong pathway

Result: Ranked list of expansion pathways by strength.

---

## 5. Implementation Notes for Phase 2

### Data Structure

Each metric calculation requires:
- `user_id`: Unique user identifier
- `category_name`: Product category
- `timestamp`: Unix millisecond timestamp (converted to UTC datetime)
- `date`: Derived UTC datetime field (not date-only unless explicitly converted during analysis)
- `user_first_date`: First review date per user per category
- `days_since_first`: Days elapsed from user's first review in category
- `review_sequence`: Sequential review number per user per category

### Edge Cases

1. **Single-review users**: Not retained (require 2+ reviews)
   - Example: User reviews Electronics once on 2023-01-05 → NOT retained

2. **Multiple reviews, same day**: Count as 1 distinct day
   - Example: Reviews at 10:00 and 14:00 on 2023-01-05 → 1 distinct day (not 2)

3. **Timezone boundaries**: Use UTC consistently
   - Example: 2023-06-30 23:59:59 UTC is still in the range; 2023-07-01 00:00:00 UTC is outside

4. **Categories with < 30 users**: Exclude from high-retention filtering
   - May still contribute data; just not eligible as high-retention destination

5. **Cross-category users**: Each category has independent retention/entry
   - Example: User A might enter via Electronics, expand to Video_Games, but NOT be retained in either

### Calculation Order

**Phase 2 implementation should follow this order:**

1. Load cleaned dataset
2. Calculate per-user, per-category retention status (is_retained)
3. Calculate per-category retention rates
4. Identify high-retention categories (top quartile + min threshold)
5. Calculate expansion pathways for all category pairs (A → B where B is high-retention)
6. Generate summary report

---

## 6. References

- **Source PDF:** `docs/course_specs/SI 507.pdf`
- **Data Spec:** `docs/DATA.md`
- **Cleaned Dataset:** `data/cleaned/cleaned_reviews.csv`
- **Quality Report:** `docs/DATA_QUALITY_REPORT.md`

---

**Status:** Draft finalized for Phase 2 implementation; requires implementation-time validation checks (cohort size, tie handling, strict window semantics)
