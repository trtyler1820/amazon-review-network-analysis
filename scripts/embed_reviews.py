#!/usr/bin/env python3
"""
Stage 2 of RAG pipeline: embed review text with sentence-transformers.

Reads data/rag/reviews_with_text.parquet, formats each row as
"title. text" (empty title/text handled gracefully), encodes with
sentence-transformers/all-MiniLM-L6-v2 (384-dim, normalized), and
writes sharded parquets to data/rag/embeddings/shard_NNNNN.parquet.

Each shard contains:
    point_id  : int64  (row index in the source parquet; stable across runs)
    embedding : list[float32]  (length 384, L2-normalized)

Sharded layout makes the run resumable: existing shards with the expected
row count are skipped on restart. A crash at hour 4 of a 7-hour run costs
you only the in-flight shard, not the whole job.

Usage:
    # Timing probe (small run into a throwaway directory)
    python3 scripts/embed_reviews.py --limit 10000 \
        --out-dir data/rag/embed_probe

    # Full run (default out-dir: data/rag/embeddings)
    python3 scripts/embed_reviews.py

    # Resume (default — existing shards skipped)
    python3 scripts/embed_reviews.py

    # Force restart
    python3 scripts/embed_reviews.py --force
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Iterable, List

import numpy as np
import polars as pl
import torch
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PARQUET = PROJECT_ROOT / "data" / "rag" / "reviews_with_text.parquet"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "rag" / "embeddings"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
DEFAULT_SHARD_SIZE = 50_000
DEFAULT_BATCH_SIZE = 128


def pick_device(preference: str) -> str:
    if preference != "auto":
        return preference
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def format_row_text(title: str | None, text: str | None) -> str:
    """Combine title + body into a single string for embedding."""
    t = (title or "").strip()
    b = (text or "").strip()
    if t and b:
        return f"{t}. {b}"
    return t or b or ""


def load_source(input_path: Path, limit: int | None) -> pl.DataFrame:
    logger.info(f"Loading {input_path}")
    cols = ["title", "text"]
    if limit:
        df = pl.read_parquet(input_path, columns=cols).head(limit)
        logger.info(f"Loaded {df.height:,} rows (--limit {limit})")
    else:
        df = pl.read_parquet(input_path, columns=cols)
        logger.info(f"Loaded {df.height:,} rows")
    return df


def iter_shards(total_rows: int, shard_size: int) -> Iterable[tuple[int, int, int]]:
    """Yield (shard_idx, start, end) triples."""
    idx = 0
    start = 0
    while start < total_rows:
        end = min(start + shard_size, total_rows)
        yield idx, start, end
        start = end
        idx += 1


def shard_path(out_dir: Path, shard_idx: int) -> Path:
    return out_dir / f"shard_{shard_idx:05d}.parquet"


def shard_is_complete(path: Path, expected_rows: int) -> bool:
    if not path.exists():
        return False
    try:
        n = pl.scan_parquet(path).select(pl.len()).collect().item()
        return n == expected_rows
    except Exception:
        return False


def encode_slice(
    model: SentenceTransformer,
    texts: List[str],
    batch_size: int,
) -> np.ndarray:
    """Encode a list of strings into an (N, 384) float32 numpy array."""
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return vectors.astype(np.float32)


def write_shard(
    path: Path, start: int, vectors: np.ndarray
) -> None:
    n = vectors.shape[0]
    point_ids = np.arange(start, start + n, dtype=np.int64)
    # Convert (N, 384) float32 to list-of-lists for polars list column
    embedding_col = [vectors[i].tolist() for i in range(n)]
    df = pl.DataFrame(
        {
            "point_id": point_ids,
            "embedding": embedding_col,
        },
        schema={
            "point_id": pl.Int64,
            "embedding": pl.List(pl.Float32),
        },
    )
    tmp = path.with_suffix(".parquet.tmp")
    df.write_parquet(tmp, compression="zstd")
    tmp.replace(path)  # atomic rename so a crash mid-write leaves no partial shard


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed review text with sentence-transformers")
    parser.add_argument("--input", type=Path, default=INPUT_PARQUET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=None, help="Limit input rows (probe)")
    parser.add_argument("--shard-size", type=int, default=DEFAULT_SHARD_SIZE)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "mps", "cuda"],
        default="auto",
    )
    parser.add_argument("--force", action="store_true", help="Delete out-dir before start")
    args = parser.parse_args()

    device = pick_device(args.device)
    logger.info(f"Device: {device}")

    out_dir: Path = args.out_dir
    if args.force and out_dir.exists():
        logger.warning(f"--force: removing {out_dir}")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_source(args.input, args.limit)
    total = df.height
    titles = df["title"].to_list()
    texts = df["text"].to_list()
    del df

    logger.info(f"Loading model: {MODEL_NAME}")
    t0 = time.perf_counter()
    model = SentenceTransformer(MODEL_NAME, device=device)
    logger.info(f"Model ready in {time.perf_counter() - t0:.1f}s")

    # Warm-up: discard the first batch's timing (model may lazy-init on device)
    logger.info("Warm-up encoding (ignored in throughput stats)")
    _ = encode_slice(model, ["warmup"] * min(args.batch_size, 32), args.batch_size)

    shards = list(iter_shards(total, args.shard_size))
    logger.info(
        f"Plan: {total:,} rows → {len(shards)} shards of up to "
        f"{args.shard_size:,} rows each (batch_size={args.batch_size})"
    )

    run_t0 = time.perf_counter()
    rows_encoded_this_run = 0
    for shard_idx, start, end in shards:
        path = shard_path(out_dir, shard_idx)
        expected = end - start
        if shard_is_complete(path, expected):
            logger.info(f"[shard {shard_idx:05d}] SKIP ({expected:,} rows already present)")
            continue

        shard_t0 = time.perf_counter()
        slice_titles = titles[start:end]
        slice_texts = texts[start:end]
        formatted = [
            format_row_text(t, x) for t, x in zip(slice_titles, slice_texts)
        ]
        vectors = encode_slice(model, formatted, args.batch_size)
        if vectors.shape != (expected, EMBED_DIM):
            raise RuntimeError(
                f"Unexpected vector shape {vectors.shape}, wanted ({expected}, {EMBED_DIM})"
            )
        write_shard(path, start, vectors)

        shard_elapsed = time.perf_counter() - shard_t0
        rows_encoded_this_run += expected
        run_elapsed = time.perf_counter() - run_t0
        rps_run = rows_encoded_this_run / run_elapsed if run_elapsed > 0 else 0.0
        rps_shard = expected / shard_elapsed if shard_elapsed > 0 else 0.0

        rows_done = end
        rows_left = total - rows_done
        eta_sec = rows_left / rps_run if rps_run > 0 else float("inf")
        eta_min = eta_sec / 60

        logger.info(
            f"[shard {shard_idx:05d}] {expected:,} rows in {shard_elapsed:.1f}s "
            f"({rps_shard:,.0f} r/s shard, {rps_run:,.0f} r/s overall)  "
            f"progress={rows_done:,}/{total:,} ({rows_done/total*100:.1f}%)  "
            f"ETA={eta_min:.1f} min"
        )

    total_elapsed = time.perf_counter() - run_t0
    logger.info("=" * 60)
    logger.info(
        f"DONE  encoded {rows_encoded_this_run:,} rows this run in "
        f"{total_elapsed:.1f}s"
    )
    if rows_encoded_this_run > 0:
        logger.info(
            f"Overall throughput: {rows_encoded_this_run/total_elapsed:,.0f} rows/sec  "
            f"(for full {total:,}-row dataset this run-rate implies "
            f"{total / (rows_encoded_this_run/total_elapsed) / 60:.1f} min)"
        )

    # Final tally across shards on disk
    all_shards = sorted(out_dir.glob("shard_*.parquet"))
    total_on_disk = 0
    for p in all_shards:
        total_on_disk += pl.scan_parquet(p).select(pl.len()).collect().item()
    logger.info(f"Shards on disk: {len(all_shards)}  total rows: {total_on_disk:,}")


if __name__ == "__main__":
    main()
