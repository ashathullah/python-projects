# Tamil OCR Quick Reference

## Installation

```bash
# PaddleOCR
python -m pip install paddlepaddle-gpu
pip install paddleocr

# ocr-tamil
pip install ocr-tamil torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

## Common Commands

### Verify Installation
```bash
python test_tamil_ocr.py
```

### Check GPU
```bash
python ocr_processor_paddle_tamil.py --check-gpu
python ocr_processor_tamil_native.py --check-gpu
```

### Process Documents

#### PaddleOCR (Best for documents)
```bash
# Tamil only
python ocr_processor_paddle_tamil.py

# Tamil + English
python ocr_processor_paddle_tamil.py --languages ta en

# Test mode
python ocr_processor_paddle_tamil.py --limit 2 --verbose
```

#### ocr-tamil (Best for scene text)
```bash
# Basic
python ocr_processor_tamil_native.py

# Test mode
python ocr_processor_tamil_native.py --limit 2
```

## Output Locations

| Script | Output Directory |
|--------|-----------------|
| PaddleOCR Tamil | `md-files-paddle-tamil/` |
| ocr-tamil | `md-files-tamil-native/` |
| Tesseract | `md-files-tesseract/` |
| PaddleOCR General | `md-files/` |

## Which One to Use?

| Use Case | Recommended |
|----------|-------------|
| High-accuracy documents | **PaddleOCR** |
| Scene text / photos | **ocr-tamil** |
| Mixed Tamil + English | **PaddleOCR** |
| Quick testing | **ocr-tamil** |
| Batch processing | **PaddleOCR** |
| Handwritten text | **ocr-tamil** |

## Command Line Options

### PaddleOCR Tamil
```
--languages ta en    # Languages (ta=Tamil, en=English)
--limit N           # Process first N folders
--verbose           # Show detailed stats
--check-gpu         # Check GPU status
--extracted PATH    # Input directory
--output PATH       # Output directory
```

### ocr-tamil
```
--limit N           # Process first N folders
--no-detection      # Skip text detection
--check-gpu         # Check GPU status
--extracted PATH    # Input directory
--output PATH       # Output directory
```

## Troubleshooting

### GPU Not Working

**PaddleOCR:**
```bash
python -c "import paddle; print(paddle.is_compiled_with_cuda())"
```

**ocr-tamil:**
```bash
python -c "import torch; print(torch.cuda.is_available())"
```

### Model Download Issues

**PaddleOCR:** Delete `~/.paddleocr/` and retry
**ocr-tamil:** Delete `~/.cache/huggingface/` and retry

## Performance

| Metric | PaddleOCR | ocr-tamil |
|--------|-----------|-----------|
| First run | ~5-10 min | ~5-10 min |
| Per page (GPU) | ~1-3 sec | ~0.5-2 sec |
| Per page (CPU) | ~5-15 sec | ~3-10 sec |
| Accuracy | 95-98% | 90-95% |

## Documentation

- **Full Guide:** [TAMIL_OCR_GUIDE.md](TAMIL_OCR_GUIDE.md)
- **Summary:** [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **Main Docs:** [README.md](README.md)
