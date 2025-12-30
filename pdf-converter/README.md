# pdf-converter

This folder contains PDFs and a one-step extractor that pulls out their “source” assets (usually page images).

## Install packages

```powershell
pip install -r pdf-converter/requirements.txt
```

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


---

## OCR Processors

Multiple OCR engines are available for processing extracted images:

### Tamil OCR (GPU-Accelerated)

#### 1. PaddleOCR with Tamil Support
High-accuracy multilingual OCR with native Tamil support.

```powershell
# Basic usage
python ocr_processor_paddle_tamil.py

# With English + Tamil
python ocr_processor_paddle_tamil.py --languages ta en

# Test with first 2 folders
python ocr_processor_paddle_tamil.py --limit 2 --verbose

# Check GPU status
python ocr_processor_paddle_tamil.py --check-gpu
```

Output: `md-files-paddle-tamil/`

**Features:**
- PP-OCRv4 models (very high accuracy)
- Native GPU acceleration via PaddlePaddle
- 80+ language support
- Excellent for batch processing

#### 2. ocr-tamil (Specialized Tamil Library)
Fine-tuned specifically for Tamil text with CRAFT + PARSEQ models.

```powershell
# Basic usage
python ocr_processor_tamil_native.py

# Test with first 2 folders
python ocr_processor_tamil_native.py --limit 2

# Check GPU status
python ocr_processor_tamil_native.py --check-gpu
```

Output: `md-files-tamil-native/`

**Features:**
- Specialized for Tamil scene and document text
- CRAFT text detection + PARSEQ recognition
- Native GPU via PyTorch/CUDA
- Very fast for single images

**See [TAMIL_OCR_GUIDE.md](TAMIL_OCR_GUIDE.md) for detailed comparison and usage.**

### Other OCR Engines

#### Tesseract OCR
```powershell
python ocr_processor_tesseract.py --languages eng+tam --limit 2
```

#### PaddleOCR (General)
```powershell
python ocr_processor_paddle.py --languages en ta --limit 2
```

---

## Testing Tamil OCR Setup

Run the verification script:

```powershell
python test_tamil_ocr.py
```

This verifies PaddleOCR, ocr-tamil, and GPU support.

---

## Performance Comparison

| Engine | Accuracy | Speed (GPU) | Tamil Support | Setup |
|--------|----------|-------------|---------------|-------|
| **PaddleOCR Tamil** | Very High | Excellent | Native | Moderate |
| **ocr-tamil** | High | Very Fast | Native | Easy |
| Tesseract | Moderate | Fast | Good | Easy |

See [TAMIL_OCR_GUIDE.md](TAMIL_OCR_GUIDE.md) for detailed documentation.
