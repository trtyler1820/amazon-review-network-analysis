# Session 8: Review Search Optimization & LLM Synthesis

**Date**: 2026-04-12 ~22:00 EDT
**Model**: Claude Sonnet 4.6 / Opus 4.6

---

## User Requests
- Debug slow Review Search queries on Streamlit dashboard (5+ min per query)
- Switch LLM synthesis from OpenAI to Google Gemini (free tier)
- Fix truncated/limited synthesis output
- Update logs

## Completed
- **Diagnosed Qdrant performance bottleneck**: 2.5M vectors in SQLite-backed local mode (12GB file) — inherently slow for large-scale vector search
- **Evaluated solutions**: Qdrant Docker vs FAISS vs collection sampling — chose sampling as lowest-effort path
- **Sampled collection**: Added `--sample` flag to `index_qdrant.py`, re-indexed 100K points (25K per category, stratified) into `data/qdrant_sample/` (496MB vs 12GB)
- **Updated `web/app.py`**: pointed to sampled collection
- **Switched LLM from OpenAI to Google Gemini**: replaced `openai` SDK with `google-generativeai`, model `gemini-2.5-flash`
- **Fixed synthesis truncation**: increased `max_output_tokens` from 900 to 12,228; attempted to disable thinking tokens (SDK too old for `ThinkingConfig`)
- **Added `parent_asin` to raw review display** in Review Search
- **Updated `.gitignore`**: added `data/qdrant_sample/`
- **Installed**: `google-generativeai`, `torchvision` (transitive dep for sentence-transformers)

## Key Decisions
- **Sampling over Docker/FAISS**: Qdrant Docker requires re-indexing (SQLite format ≠ server format) AND Docker as dependency. FAISS lacks built-in metadata filtering and payload storage. Sampling keeps all existing code intact with zero infrastructure changes.
- **100K sample size**: 25K per category, stratified. Software (27K total) is nearly fully represented. Sufficient for demo and all filter combinations.
- **Gemini over OpenAI**: Tyler's OpenAI API had no credits; Gemini free tier available after enabling billing on Google Cloud.

## Blockers / Notes
- Qdrant Docker remains an option for future scaling if needed
- The `--sample` arg was removed from `index_qdrant.py` by user (reverted to original)
- Gemini 2.5 Flash uses thinking tokens by default which may consume part of output budget; SDK version doesn't support `ThinkingConfig` to disable

## Next Steps
1. Phase 4 finalization: polish docs, final test pass
2. Consider adding config.py for centralized path management (~40-60K token task)
3. Fill in README TODOs (Key Findings, demo video)
4. Deadline: April 24, 2026
