# pdf-converter

This folder contains PDFs and a one-step extractor that pulls out their “source” assets (usually page images).

## One-step run

From the repo root:

```powershell
python pdf-converter/extract_source.py
```

Outputs to: `pdf-converter/extracted/<pdf-name>/`

## Options

- Extract embedded images + render pages:
  - `python pdf-converter/extract_source.py --extract both --dpi 200`
- Also write extracted text:
  - `python pdf-converter/extract_source.py --write-text`

