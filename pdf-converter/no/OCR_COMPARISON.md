# OCR Performance Comparison

This project includes multiple OCR processing scripts for performance comparison.

## Scripts

### 1. ocr_processor.py (GPU-Accelerated EasyOCR)
Uses EasyOCR with GPU support for fastest processing.

```bash
python ocr_processor.py --languages en ta --limit 1
```

**Output**: `md-files/`

### 2. ocr_processor_cpu.py (CPU-Only EasyOCR)
Uses EasyOCR with CPU-only processing for comparison.

```bash
python ocr_processor_cpu.py --languages en ta --limit 1
```

**Output**: `md-files-cpu/`

### 3. ocr_processor_tesseract.py (Tesseract OCR)
Uses Tesseract OCR engine (requires Tesseract installed on system).

```bash
python ocr_processor_tesseract.py --languages eng+tam --limit 1
```

**Output**: `md-files-tesseract/`

**Note**: Download Tesseract from https://github.com/UB-Mannheim/tesseract/wiki

### 4. compare_ocr_performance.py (Comparison Script)
Runs all three scripts and compares performance.

```bash
python compare_ocr_performance.py --limit 1 --languages en
```

## Performance Metrics

Each script tracks and displays:
- **Initialization time**: Time to load OCR models
- **Per-image processing time**: Time to process each individual image
- **Total processing time**: Total time for all images
- **Average processing time**: Average time per image

## Language Codes

### EasyOCR (ocr_processor.py, ocr_processor_cpu.py)
- English: `en`
- Tamil: `ta`
- Hindi: `hi`
- Telugu: `te`
- Kannada: `ka`
- Marathi: `mr`

Example: `--languages en ta`

### Tesseract (ocr_processor_tesseract.py)
- English: `eng`
- Tamil: `tam`
- Hindi: `hin`
- Telugu: `tel`
- Kannada: `kan`
- Marathi: `mar`

Example: `--languages eng+tam`

## Requirements

```bash
# For EasyOCR (GPU and CPU versions)
pip install torch torchvision easyocr

# For GPU support (CUDA 12.1)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# For Tesseract
pip install pytesseract pillow
# Download Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
```

## Expected Performance

Typical processing times (may vary based on hardware):
- **GPU EasyOCR**: 0.5-2 seconds per image
- **CPU EasyOCR**: 3-10 seconds per image
- **Tesseract**: 0.2-1 second per image

*Note: GPU performance depends on GPU model and CUDA version.*
