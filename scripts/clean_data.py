#!/usr/bin/env python3
"""
Data Cleaning Pipeline for Amazon Reviews Analysis

This script cleans Amazon review data with the following steps:
1. Load data from JSONL files
2. Filter by verified_purchase = True
3. Filter by date range (Jan 2023 - Jun 2023)
4. Group by parent_asin to deduplicate variants
5. Remove duplicates by (user_id, parent_asin, timestamp)
6. Derive retention analysis columns
7. Export cleaned dataset and generate quality report

Usage:
    python clean_data.py [--sample-size N] [--output-dir DIR]

Default: Loads all data; use --sample-size 25 to test on 25 records per file.
"""

import json
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration - paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"  # Raw JSONL files
OUTPUT_DIR = PROJECT_ROOT / "data" / "cleaned"
DOCS_DIR = PROJECT_ROOT / "docs"

# Review files (primary data)
REVIEW_FILES = {
    "Cell_Phones_and_Accessories": "Cell_Phones_and_Accessories.jsonl",
    "Electronics": "Electronics.jsonl",
    "Software": "Software.jsonl",
    "Video_Games": "Video_Games.jsonl",
}

# Date range (from SI 507 v2 PDF)
# Using UTC timezone to ensure consistent, reproducible results across environments
DATE_START = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
DATE_END = datetime(2023, 7, 1, 0, 0, 0, tzinfo=timezone.utc)  # Use next day boundary to include all of June 30


class DataCleaner:
    """Handles all data cleaning operations with detailed logging."""

    def __init__(self, sample_size=None, output_dir=None):
        """
        Initialize cleaner.

        Args:
            sample_size: If set, only load first N records per file (for testing)
            output_dir: Optional custom output directory (defaults to global OUTPUT_DIR)
        """
        self.sample_size = sample_size
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
        self.docs_dir = DOCS_DIR
        self.cleaning_log = {}  # Track row counts at each step
        self.cleaned_data = None

    def load_reviews(self, category: str) -> pd.DataFrame:
        """
        Load review data from JSONL file.

        Args:
            category: Category name (key in REVIEW_FILES)

        Returns:
            DataFrame with raw review data
        """
        filepath = DATA_DIR / REVIEW_FILES[category]
        logger.info(f"Loading reviews from {category}...")

        records = []
        with open(filepath, 'r') as f:
            for i, line in enumerate(f):
                if self.sample_size and i >= self.sample_size:
                    break
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipped malformed JSON at line {i}: {e}")

        df = pd.DataFrame(records)
        logger.info(f"Loaded {len(df)} records from {category}")
        return df

    def convert_timestamp(self, ts_milliseconds: int) -> datetime:
        """
        Convert millisecond timestamp to UTC datetime.

        Uses UTC timezone for reproducible results across environments.
        This ensures consistent date boundaries regardless of machine timezone.
        """
        try:
            return datetime.fromtimestamp(ts_milliseconds / 1000, tz=timezone.utc)
        except (ValueError, OSError, OverflowError, TypeError):
            return None

    def filter_verified_purchase(self, df: pd.DataFrame, category: str) -> pd.DataFrame:
        """
        Filter to verified_purchase = True only.

        Calculation:
        - Counts rows where verified_purchase == True
        - Logs row count before/after
        """
        before_count = len(df)
        df_filtered = df[df['verified_purchase'] == True].copy()
        after_count = len(df_filtered)

        filtered_out = before_count - after_count
        pct_retained = (after_count / before_count * 100) if before_count > 0 else 0

        logger.info(
            f"[{category}] verified_purchase filter: {before_count} → {after_count} "
            f"({filtered_out} removed, {pct_retained:.1f}% retained)"
        )

        if category not in self.cleaning_log:
            self.cleaning_log[category] = {}
        self.cleaning_log[category]['after_verified_purchase'] = {
            'count': after_count,
            'removed': filtered_out,
            'pct_retained': pct_retained
        }

        return df_filtered

    def filter_date_range(self, df: pd.DataFrame, category: str) -> pd.DataFrame:
        """
        Filter to date range: Jan 1, 2023 - Jun 30, 2023 (inclusive, UTC timezone).

        Calculation:
        - Converts timestamp (milliseconds) to UTC datetime
        - Filters to [DATE_START, DATE_END) to include full day of June 30
        - Uses DATE_END = July 1, 2023 00:00:00 UTC as boundary (exclusive)
        - Logs rows before/after

        Timezone Policy:
        - All timestamps converted to UTC for reproducibility across environments
        - This ensures consistent date boundaries regardless of machine timezone
        """
        before_count = len(df)

        # Convert timestamp to datetime (UTC) - vectorized for performance
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True, errors='coerce')

        # Filter to date range (inclusive: includes full day of June 30)
        df_filtered = df[
            (df['date'] >= DATE_START) &
            (df['date'] < DATE_END)
        ].copy()

        after_count = len(df_filtered)
        filtered_out = before_count - after_count
        pct_retained = (after_count / before_count * 100) if before_count > 0 else 0

        logger.info(
            f"[{category}] date range filter (2023-01-01 to 2023-06-30 inclusive, UTC): {before_count} → {after_count} "
            f"({filtered_out} removed, {pct_retained:.1f}% retained)"
        )

        self.cleaning_log[category]['after_date_filter'] = {
            'count': after_count,
            'removed': filtered_out,
            'pct_retained': pct_retained
        }

        return df_filtered

    def deduplicate_variants(self, df: pd.DataFrame, category: str) -> pd.DataFrame:
        """
        Group by parent_asin to deduplicate variants.

        Calculation:
        - parent_asin = product model (e.g., "iPhone case")
        - asin = product variant (e.g., "red iPhone case")
        - We keep all reviews but group by parent_asin for analysis
        - This step documents the grouping (doesn't reduce rows at this stage)
        """
        before_count = len(df)
        unique_parent_asins = df['parent_asin'].nunique()
        unique_asins = df['asin'].nunique()

        logger.info(
            f"[{category}] variant deduplication: {before_count} reviews, "
            f"{unique_asins} unique ASINs, {unique_parent_asins} unique parent ASINs"
        )

        self.cleaning_log[category]['variant_grouping'] = {
            'total_reviews': before_count,
            'unique_asins': unique_asins,
            'unique_parent_asins': unique_parent_asins,
            'variant_ratio': unique_asins / unique_parent_asins if unique_parent_asins > 0 else 1
        }

        return df

    def remove_duplicate_reviews(self, df: pd.DataFrame, category: str) -> pd.DataFrame:
        """
        Remove duplicate (user_id, parent_asin, timestamp) combinations.

        Calculation:
        - A duplicate occurs when same user reviews same product (parent_asin) at exact same timestamp
        - We keep the first occurrence, remove subsequent ones (deduplicates exact timestamp matches)
        - Note: Multiple reviews on same day by same user/product are preserved (different timestamps)
        - Logs: rows removed due to duplication
        """
        before_count = len(df)

        # Remove duplicates: keep first occurrence of (user_id, parent_asin, timestamp)
        df_deduped = df.drop_duplicates(
            subset=['user_id', 'parent_asin', 'timestamp'],
            keep='first'
        ).copy()

        after_count = len(df_deduped)
        duplicates_removed = before_count - after_count
        pct_retained = (after_count / before_count * 100) if before_count > 0 else 0

        logger.info(
            f"[{category}] duplicate removal (user_id, parent_asin, timestamp): {before_count} → {after_count} "
            f"({duplicates_removed} duplicates removed, {pct_retained:.1f}% retained)"
        )

        self.cleaning_log[category]['after_deduplication'] = {
            'count': after_count,
            'duplicates_removed': duplicates_removed,
            'pct_retained': pct_retained
        }

        return df_deduped

    def derive_retention_columns(self, df: pd.DataFrame, category: str) -> pd.DataFrame:
        """
        Derive columns for retention analysis.

        Adds:
        - user_first_date: First date user reviewed in this category
        - days_since_first: Number of days since user's first review
        - review_sequence: Review number in sequence for this user in this category

        Calculation logic:
        - Group by user_id
        - Sort by timestamp
        - user_first_date = min(timestamp) per user
        - days_since_first = (timestamp - user_first_date).days
        - review_sequence = rank by timestamp
        """
        # Sort by user and timestamp
        df = df.sort_values(['user_id', 'timestamp']).copy()

        # user_first_date: first review date for each user
        df['user_first_date'] = df.groupby('user_id')['date'].transform('min')

        # days_since_first: days from first review
        df['days_since_first'] = (df['date'] - df['user_first_date']).dt.days

        # review_sequence: review number for this user (1, 2, 3, ...)
        df['review_sequence'] = df.groupby('user_id').cumcount() + 1

        logger.info(f"[{category}] derived retention columns: user_first_date, days_since_first, review_sequence")

        return df

    def validate_nulls(self, df: pd.DataFrame, category: str) -> Tuple[pd.DataFrame, Dict]:
        """
        Check for null values in critical fields.

        Critical fields: user_id, parent_asin, timestamp, verified_purchase, date, rating
        (category_name is added after this check)
        """
        critical_fields = ['user_id', 'parent_asin', 'timestamp', 'verified_purchase', 'date', 'rating']
        null_counts = {}

        for field in critical_fields:
            if field in df.columns:
                null_count = df[field].isnull().sum()
                null_counts[field] = null_count
                if null_count > 0:
                    logger.warning(f"[{category}] {field}: {null_count} null values")

        # Log summary
        total_nulls = sum(null_counts.values())
        logger.info(f"[{category}] null check: {total_nulls} total nulls in critical fields")

        return df, null_counts

    def clean_category(self, category: str) -> pd.DataFrame:
        """
        Execute full cleaning pipeline for a category.

        Returns cleaned DataFrame.
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"CLEANING: {category}")
        logger.info(f"{'='*80}")

        # Initialize category log
        self.cleaning_log[category] = {
            'raw_count': None,
            'final_count': None
        }

        # Load raw data
        df = self.load_reviews(category)
        self.cleaning_log[category]['raw_count'] = len(df)

        # Filter: verified_purchase = True
        df = self.filter_verified_purchase(df, category)

        # Filter: date range (2023-01-01 to 2023-06-30)
        df = self.filter_date_range(df, category)

        # Document variant grouping
        df = self.deduplicate_variants(df, category)

        # Remove duplicate reviews
        df = self.remove_duplicate_reviews(df, category)

        # Derive retention columns
        df = self.derive_retention_columns(df, category)

        # Validate nulls
        df, null_counts = self.validate_nulls(df, category)

        # Record final count
        self.cleaning_log[category]['final_count'] = len(df)

        logger.info(f"[{category}] FINAL: {self.cleaning_log[category]['raw_count']} → {len(df)} records")

        # Add category column
        df['category_name'] = category

        return df

    def clean_all_files(self) -> pd.DataFrame:
        """Clean all review files and combine."""
        all_dfs = []

        for category in REVIEW_FILES.keys():
            try:
                df_cleaned = self.clean_category(category)
                all_dfs.append(df_cleaned)
            except Exception as e:
                logger.error(f"Error cleaning {category}: {e}")

        # Combine all cleaned data
        if all_dfs:
            self.cleaned_data = pd.concat(all_dfs, ignore_index=True)
            logger.info(f"\n{'='*80}")
            logger.info(f"COMBINED: {len(self.cleaned_data)} total records across all categories")
            logger.info(f"{'='*80}")
        else:
            logger.error("No data was successfully cleaned!")
            self.cleaned_data = pd.DataFrame()

        return self.cleaned_data

    def select_output_columns(self) -> pd.DataFrame:
        """
        Select relevant columns for analysis.

        Output Schema (12 columns):
        - user_id: Unique user identifier
        - parent_asin: Product model identifier (for grouping variants)
        - asin: Product variant identifier
        - timestamp: Original millisecond timestamp
        - date: Converted UTC datetime
        - rating: Review rating (1-5)
        - verified_purchase: Boolean flag (always True in cleaned data)
        - category_name: Product category
        - helpful_vote: Count of helpful votes (numeric, non-negative)
        - user_first_date: User's first review date in this category
        - days_since_first: Days elapsed from user's first review in category
        - review_sequence: Review sequence number for user in category
        """
        output_columns = [
            'user_id', 'parent_asin', 'asin', 'timestamp', 'date',
            'rating', 'verified_purchase', 'category_name', 'helpful_vote',
            'user_first_date', 'days_since_first', 'review_sequence'
        ]

        # Keep only columns that exist
        available_columns = [col for col in output_columns if col in self.cleaned_data.columns]
        return self.cleaned_data[available_columns]

    def save_cleaned_data(self):
        """Save cleaned data to CSV and generate quality report."""
        if self.cleaned_data is None or len(self.cleaned_data) == 0:
            logger.error("No cleaned data to save!")
            return

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Select output columns
        df_output = self.select_output_columns()

        # Save to CSV
        output_file = self.output_dir / "cleaned_reviews.csv"
        df_output.to_csv(output_file, index=False)
        logger.info(f"Cleaned data saved to: {output_file}")

        # Try to save to Parquet (more efficient for large files)
        try:
            output_file_parquet = self.output_dir / "cleaned_reviews.parquet"
            df_output.to_parquet(output_file_parquet, index=False)
            logger.info(f"Cleaned data saved to: {output_file_parquet}")
        except ImportError:
            logger.warning("Parquet export skipped (pyarrow not installed). CSV format available.")

    def generate_quality_report(self):
        """Generate and save data quality report."""
        report = []
        report.append("# Data Quality Report\n")
        report.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        report.append(f"Sample Size: {self.sample_size if self.sample_size else 'Full dataset'}\n\n")

        report.append("## Summary\n")
        report.append(f"- Total records loaded: {sum(self.cleaning_log[cat]['raw_count'] for cat in self.cleaning_log)}\n")
        report.append(f"- Total records after cleaning: {len(self.cleaned_data)}\n")
        report.append(f"- Unique categories: {self.cleaned_data['category_name'].nunique()}\n")
        report.append(f"- Unique users: {self.cleaned_data['user_id'].nunique()}\n")
        report.append(f"- Unique products (parent_asin): {self.cleaned_data['parent_asin'].nunique()}\n")
        report.append(f"- Date range: {self.cleaned_data['date'].min()} to {self.cleaned_data['date'].max()}\n\n")

        report.append("## Filtering Impact by Category\n\n")

        for category in REVIEW_FILES.keys():
            if category not in self.cleaning_log:
                continue

            log = self.cleaning_log[category]
            report.append(f"### {category}\n")
            report.append(f"- Raw count: {log['raw_count']}\n")

            if 'after_verified_purchase' in log:
                vp = log['after_verified_purchase']
                report.append(f"- After verified_purchase filter: {vp['count']} ({vp['pct_retained']:.1f}% retained)\n")

            if 'after_date_filter' in log:
                df = log['after_date_filter']
                report.append(f"- After date filter (2023-01-01 to 2023-06-30): {df['count']} ({df['pct_retained']:.1f}% retained)\n")

            if 'after_deduplication' in log:
                dd = log['after_deduplication']
                report.append(f"- After deduplication: {dd['count']} ({dd['pct_retained']:.1f}% retained)\n")

            if 'variant_grouping' in log:
                vg = log['variant_grouping']
                report.append(f"- Variant analysis: {vg['unique_asins']} ASINs → {vg['unique_parent_asins']} parent ASINs (ratio: {vg['variant_ratio']:.2f}x)\n")

            report.append(f"- **Final count: {log['final_count']}**\n\n")

        report.append("## Data Quality Checks (Computed)\n")

        # Compute actual checks from data
        check_user_id = "✓" if self.cleaned_data['user_id'].isnull().sum() == 0 else "✗"
        check_parent_asin = "✓" if self.cleaned_data['parent_asin'].isnull().sum() == 0 else "✗"
        check_timestamp = "✓" if self.cleaned_data['timestamp'].isnull().sum() == 0 else "✗"
        check_verified = "✓" if (self.cleaned_data['verified_purchase'] == True).all() else "✗"
        check_date_min = self.cleaned_data['date'].min().strftime('%Y-%m-%d')
        check_date_max = self.cleaned_data['date'].max().strftime('%Y-%m-%d')
        check_date_range = "✓" if (check_date_min >= '2023-01-01') and (check_date_max <= '2023-06-30') else "✗"
        check_rating = "✓" if (self.cleaned_data['rating'].isnull().sum() == 0) and (self.cleaned_data['rating'].between(1, 5).all()) else "✗"
        check_category = "✓" if self.cleaned_data['category_name'].isnull().sum() == 0 else "✗"

        report.append(f"- All records have user_id (no nulls): {check_user_id}\n")
        report.append(f"- All records have parent_asin (no nulls): {check_parent_asin}\n")
        report.append(f"- All records have timestamp (no nulls): {check_timestamp}\n")
        report.append(f"- All records have verified_purchase = True: {check_verified}\n")
        report.append(f"- All records have category_name (no nulls): {check_category}\n")
        report.append(f"- All records have valid rating [1-5] (no nulls): {check_rating}\n")
        report.append(f"- Date range check: {check_date_min} to {check_date_max} [within 2023-01-01 to 2023-06-30]: {check_date_range}\n\n")

        report.append("## Retention Analysis Readiness\n")
        report.append(f"- Minimum users per category: {self.cleaned_data.groupby('category_name')['user_id'].nunique().min()}\n")
        report.append(f"- Average days per user: {self.cleaned_data.groupby('user_id')['days_since_first'].max().mean():.1f}\n")
        report.append("- Review sequence column derived ✓\n")
        report.append("- user_first_date calculated ✓\n")

        report_text = "".join(report)

        # Save report (to docs directory)
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        report_file = self.docs_dir / "DATA_QUALITY_REPORT.md"
        with open(report_file, 'w') as f:
            f.write(report_text)
        logger.info(f"Quality report saved to: {report_file}")

        # Also print report
        print("\n" + "="*80)
        print("DATA QUALITY REPORT")
        print("="*80)
        print(report_text)


def main():
    parser = argparse.ArgumentParser(description="Clean Amazon reviews data")
    parser.add_argument('--sample-size', type=int, default=None,
                        help='Load only first N records per file (for testing)')
    parser.add_argument('--output-dir', type=str, default=str(OUTPUT_DIR),
                        help='Output directory for cleaned data')

    args = parser.parse_args()

    # Create cleaner and run pipeline
    cleaner = DataCleaner(sample_size=args.sample_size, output_dir=args.output_dir)
    cleaner.clean_all_files()
    cleaner.save_cleaned_data()
    cleaner.generate_quality_report()

    logger.info("\n✓ Data cleaning complete!")


if __name__ == "__main__":
    main()
