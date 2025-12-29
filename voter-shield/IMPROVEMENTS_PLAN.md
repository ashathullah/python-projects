# VoterShield Improvements Plan (Accuracy, Speed, Scale)

## Goals

1. Increase extraction accuracy across English + Tamil rolls.
2. Increase speed by parallelizing OCR safely (bounded concurrency).
3. Capture first-page information (cover/header metadata).
4. Capture last-page totals for completeness validation (Tamil label: "&#x0BAE;&#x0BCA;&#x0BA4;&#x0BCD;&#x0BA4;&#x0BAE;&#x0BCD;" i.e., "மொத்தம்").
5. Scale to ~80K PDFs (local or S3) with progress tracking and resume-from-interrupt.

Non-goals (for now): realtime UI, database persistence, analytics/visualization.

---

## Reference Input (Example)

- `pdf/2026-EROLLGEN-S22-114-SIR-DraftRoll-Revision1-TAM-1-WI.pdf`

This plan targets adding the maximum reliable datapoints extractable from this style of electoral roll PDF.

---

## Current Strategy (What Works Today)

- Fixed-layout page model: voter pages are treated as a 10x3 grid (layout-driven cropping).
- Deterministic splitting: injected `VOTER_END` marker enables stable text splitting (no position heuristics).
- Speed optimization: per page, 30 crops are stacked into one image and OCR'd once, then split back into 30 blocks.
- Quality gate: ruff + black + regression test (`tests/test_pipeline_regression.py`).

---

## Target Output: Superset Schema (All Extractable Data Points)

### A) Document-level metadata (cover pages / headers)

These are fields we should attempt to extract once per PDF and then stamp on every voter row:

- Source: `source_pdf_name`, `source_pdf_path`, `source_s3_uri` (if any), `doc_id`
- Roll identity: `roll_type` (Draft/Final/SIR), `revision`/`revision_no`, `publication_date`/`as_of_date` (if present)
- Geography: `state_name`, `district_name`, `taluk`/`mandal`/`block` (if present), `ward`/`panchayat`/`municipality` (if present)
- Constituencies:
  - `assembly_constituency_no`, `assembly_constituency_name`
  - `parliamentary_constituency_no`, `parliamentary_constituency_name` (if present)
- Part/booth: `part_no`, `part_name`/`part_area_name` (if present)
- Polling station: `polling_station_no`, `polling_station_name`, `polling_station_address`, `pin_code` (if present)

### B) Page-level metadata (per voter grid page)

These come from page header/section text and are stamped on each voter record for that page:

- `page_no` (from filename + sanity check against OCR header if available)
- `section_no`, `section_name` (street/ward text; Tamil + English parsing variants)
- Optional: `booth_id` / `part_id` if printed in page header/footer

### C) Voter-level fields (each record)

Core structured voter record output:

- Ordering: `serial_no` (reset per PDF), `voter_no` (1..30 within page if grid order is kept)
- Identity: `epic_id`, `name`
- Relationship:
  - `relation_type` (Father/Mother/Husband/Other)
  - `relative_name` (normalized single field) OR separate columns (`father_name`, `mother_name`, `husband_name`, `other_name`)
- Household: `house_no`
- Demographics: `age`, `gender` (M/F/T if present)

Optional/advanced (only if reliable):

- `photo_present` (boolean)
- bilingual fields if present: `name_local`, `name_english` (only when roll prints both)

### D) Summary / totals (last page)

Extract once per PDF:

- `total_male`, `total_female`, `total_third_gender` (if shown)
- `total_voters_expected` (from the "&#x0BAE;&#x0BCA;&#x0BA4;&#x0BCD;&#x0BA4;&#x0BAE;&#x0BCD;" row/cell)

### E) Quality + operational fields (batch observability)

These are not "citizen data", but required for debugging and scale:

- Versioning: `pipeline_version` (git SHA), `run_id`
- Timing: `started_at_utc`, `finished_at_utc`, `duration_ms`
- OCR config: `ocr_engine` (tesseract), `ocr_lang`, `dpi`, `psm_profile`
- Counts: `pages_total`, `pages_processed`, `extracted_voters`
- Integrity: `marker_splits_total`, `marker_splits_min_page`, `marker_splits_failed_pages`
- Completeness: `completeness_ratio` (= extracted_voters / total_voters_expected when available)
- Diagnostics: `warnings`, `error`

---

## Scale Requirements (~80K PDFs): Processing Flow, Progress File, Resume

### Desired flow

1. Enumerate input PDFs (local directory OR S3 prefix).
2. For each PDF:
   - Process it end-to-end.
   - Write `csv/<pdf_stem>.csv`.
   - Update progress tracking files as the PDF advances through stages.
3. If interrupted:
   - Skip PDFs already marked `completed`.
   - Any PDF marked `in_progress` should be treated as `pending` and processed again.

### Output naming

- Output CSV per input PDF: `csv/<pdf_stem>.csv`
- Optional: per-PDF report JSON: `csv/<pdf_stem>.report.json`

### Progress tracking (recommended design)

Use two files per run:

1) Append-only event log (durable):
- `runs/<run_id>/events.jsonl`
- Each line is a JSON event (safe to append even during crashes).

2) Snapshot table (human readable):
- `runs/<run_id>/progress.csv`
- Rewritten periodically from the current state (Excel-friendly).

### Resume semantics

- State machine per PDF: `pending -> in_progress -> completed|failed`
- On startup with `--resume`:
  - load existing run state
  - reset any `in_progress` items to `pending` (reprocess)
  - continue with remaining `pending` and optionally `failed` (configurable)

### Atomic outputs (to avoid partial CSVs)

- Always write to `csv/<pdf_stem>.csv.tmp` then rename to `csv/<pdf_stem>.csv` only on success.
- Optionally remove any prior `.tmp` on startup.

### Minimum columns for `progress.csv`

This satisfies your required fields and adds the minimum useful operational context:

- `pdf_name`
- `source` (local path or `s3://...`)
- `status` (`pending|in_progress|completed|failed`)
- `stage` (`download|convert|crop|ocr|parse|validate|write|upload`)
- `progress` (free text, e.g. `pages 12/24`)
- `progress_percentage` (0..100)
- `accuracy` (recommended: define as completeness; see below)
- `extracted_voters`
- `total_voters_expected` (from "மொத்தம்" when available)
- `output_csv`
- `started_at`, `finished_at`, `duration_ms`
- `error` (short string)

### What "accuracy" should mean at batch scale

Without a golden baseline per PDF, "accuracy" must be operationally defined:

- If `total_voters_expected` is available: `accuracy = extracted_voters / total_voters_expected`
- Otherwise: derive a score from integrity checks:
  - expected splits per grid page ~ 30
  - penalize pages with low marker splits or excessive missing required fields

This avoids claiming semantic correctness when we only have completeness signals.

---

## Pipeline Improvements (Accuracy + Speed)

### 1) Process first and last pages (metadata + totals)

Current issue:
- conversion skips initial pages and drops the final page (`pdf_to_png.py`)

Fix:
- Convert 3 page classes:
  1) cover pages (page 1..Ncover) -> extract document metadata
  2) voter pages (grid pages) -> crop + OCR + parse voters
  3) last page (summary) -> extract totals ("மொத்தம்") and validate completeness

### 2) Parallel OCR safely (big speed win)

Keep "stack 30 crops -> single OCR" but parallelize at the page level:

- `ocr_workers`: number of concurrent OCR tasks (bounded)
- Avoid nested parallelism:
  - if you run multiple PDFs in parallel, reduce `pdf2image` internal threads

Preferred parallelization model:
- Parallelize across pages (and optionally across PDFs) with explicit worker pools.
- Keep conversion and OCR as separate stages so concurrency is centralized and controllable.

### 3) Integrity checks (accuracy and debuggability)

Add validations:

- Per grid page, expected voter blocks ~ 30:
  - if splits < threshold (e.g. < 25), treat page as OCR failure and write a debug bundle
- Per PDF:
  - if `total_voters_expected` exists and differs from extracted -> mark incomplete (strict vs soft mode)

Debug bundle contents (per failing page/PDF):

- stacked crop image
- OCR text output
- split count + detected `VOTER_END` hits

### 4) Improve EPIC extraction (reduce false/missing IDs)

Current English EPIC parsing is heuristic. Improve by:

- OCR the EPIC region using a dedicated crop + whitelist config (pattern already exists in codebase).
- Normalize common OCR confusions (O/0, I/1, Y/V) only for EPIC candidates.
- Validate with strict regex (2-4 letters + 6-8 digits), store `epic_id_raw` and `epic_id_normalized` if needed.

### 5) OCR preprocessing profiles

Introduce preprocessing presets:

- Stacked voter text: grayscale -> contrast -> threshold -> optional sharpen
- Summary totals cells: tighter crop, `--psm 7/8`, aggressive threshold
- Cover metadata: `--psm 6`, moderate threshold

---

## Implementation Plan (Phased)

### Phase 0 - Batch-safe foundations

- Create required dirs at runtime (`pdf/`, `jpg/`, `crops/`, `ocr/`, `csv/`, `runs/`, `logs/`).
- Add run state store (`runs/<run_id>/events.jsonl` + `runs/<run_id>/progress.csv`).
- Refactor output to one CSV per PDF (`csv/<pdf_stem>.csv`) with atomic writes.

Acceptance:
- Can process a folder of PDFs and see live progress updates; restart resumes and reprocesses only `in_progress`.

### Phase 1 - Controlled parallelism

- Add CLI/config: `--pdf-workers`, `--ocr-workers`, `--resume`, `--strict`, `--state-dir`.
- Remove hardcoded `max_workers = 1` and prevent nested parallelism explosions.

Acceptance:
- Measurable throughput improvement without runaway threads/memory.

### Phase 2 - Decouple crop from OCR

- Cropping produces stacked images only.
- OCR stage discovers stacked images and OCRs them in parallel into per-page text files.

Acceptance:
- Outputs match current regression baseline for the existing fixture(s).

### Phase 3 - First/last page extraction

- Implement cover metadata extraction (page 1..Ncover).
- Implement summary totals extraction (last page) and completeness validation based on "மொத்தம்".

Acceptance:
- For the sample PDF, extracted total equals the last-page total and mismatches are reported.

### Phase 4 - Accuracy upgrades

- Proportional marker placement (remove hardcoded pixel offsets).
- Page split integrity checks + debug bundles.
- Dedicated EPIC OCR + strict validation.

Acceptance:
- Fewer missing EPIC IDs and fewer pages with low split counts.

### Phase 5 - Tests + diagnostics

- Unit tests for:
  - summary totals parsing
  - cover metadata parsing
  - integrity checks (synthetic OCR text)
- Extend regression tests carefully (fixtures kept small).

Acceptance:
- Quality gate passes and failures are actionable (clear diffs + report files).

---

## Runtime Parity Note (Important)

- `pdf2image` requires Poppler on Windows; Docker image installs Poppler (`poppler-utils`).
- For 80K runs, prefer Docker/ECS to keep conversion + OCR consistent across machines.

---

## Open Decisions (Need Confirmation)

1) Validation strictness:
- Hard fail if extracted voters != last-page total ("மொத்தம்")
- OR soft fail: still write CSV + mark `failed`/`incomplete` in progress + optional `--strict` to exit non-zero

2) Parallelism scope:
- Parallelize across pages within one PDF only
- OR also parallelize across PDFs (requires tighter resource controls)

