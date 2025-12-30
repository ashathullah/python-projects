# Tamil OCR Implementation Guide

This project now includes two specialized scripts for Tamil OCR with GPU acceleration support.

## Available Scripts

### 1. PaddleOCR with Tamil Support
**File:** `ocr_processor_paddle_tamil.py`

**Features:**
- High accuracy using PP-OCRv4 models
- Native GPU acceleration via PaddlePaddle
- Multilingual support (Tamil + English + 80+ languages)
- Excellent for batch processing
- Automatic model download on first run

**Installation:**
```bash
# Install PaddlePaddle GPU (requires CUDA/cuDNN)
python -m pip install paddlepaddle-gpu

# Install PaddleOCR
pip install paddleocr
```

**Usage:**
```bash
# Basic usage (Tamil only)
python ocr_processor_paddle_tamil.py

# Tamil + English
python ocr_processor_paddle_tamil.py --languages ta en

# Process first 2 folders only
python ocr_processor_paddle_tamil.py --limit 2

# Check GPU status
python ocr_processor_paddle_tamil.py --check-gpu

# Verbose mode with OCR statistics
python ocr_processor_paddle_tamil.py --verbose
```

**Output:** `md-files-paddle-tamil/`

---

### 2. ocr-tamil (Specialized Tamil Library)
**File:** `ocr_processor_tamil_native.py`

**Features:**
- Specifically fine-tuned for Tamil text
- Uses CRAFT (text detection) + PARSEQ (recognition) models
- Excellent for scene text and "in-the-wild" images
- Native GPU via PyTorch/CUDA
- Very fast for single/scene images

**Installation:**
```bash
# Install ocr-tamil
pip install ocr-tamil

# For GPU support, install PyTorch with CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

**Usage:**
```bash
# Basic usage
python ocr_processor_tamil_native.py

# Process first 2 folders only
python ocr_processor_tamil_native.py --limit 2

# Check GPU status
python ocr_processor_tamil_native.py --check-gpu

# Disable text detection (if entire image is text)
python ocr_processor_tamil_native.py --no-detection
```

**Output:** `md-files-tamil-native/`

---

## Comparison

| Feature | PaddleOCR Tamil | ocr-tamil Native |
|---------|----------------|------------------|
| **Accuracy** | Very High (PP-OCRv4) | High (Fine-tuned for Tamil) |
| **GPU Support** | Native (PaddlePaddle GPU) | Native (PyTorch CUDA) |
| **Setup Complexity** | Moderate | Easy |
| **Speed** | Excellent for batch | Very fast for single images |
| **Language Support** | Multilingual (80+) | Tamil + English only |
| **Scene Text** | Good | Excellent (CRAFT model) |
| **Document Text** | Excellent | Very Good |
| **Model Size** | Moderate | Moderate |

---

## GPU Requirements

Both scripts require NVIDIA GPU with CUDA support for GPU acceleration:

- **CUDA:** 11.x or 12.x
- **cuDNN:** Compatible version
- **GPU Memory:** 4GB+ recommended
- **Compute Capability:** 3.5+

### Checking GPU Status

Both scripts include GPU status checking:

```bash
# Check PaddleOCR GPU status
python ocr_processor_paddle_tamil.py --check-gpu

# Check ocr-tamil GPU status
python ocr_processor_tamil_native.py --check-gpu
```

---

## Recommendations

### Use **PaddleOCR** (`ocr_processor_paddle_tamil.py`) if:
- You need multilingual support (Tamil + English + others)
- Processing large batches of documents
- Require highest accuracy for printed text
- Need production-grade reliability

### Use **ocr-tamil** (`ocr_processor_tamil_native.py`) if:
- Working exclusively with Tamil text
- Processing scene text (photos, signboards, etc.)
- Need simpler setup
- Want PyTorch-based solution

---

## Troubleshooting

### PaddleOCR Issues

1. **GPU not detected:**
   ```bash
   # Verify PaddlePaddle CUDA installation
   python -c "import paddle; print(paddle.is_compiled_with_cuda())"
   ```

2. **Model download errors:**
   - First run downloads models automatically
   - Ensure stable internet connection
   - Models stored in `~/.paddleocr/`

3. **Language not supported:**
   - Use `--languages ta` for Tamil
   - Use `--languages en` for English
   - Use `--languages ta en` for both

### ocr-tamil Issues

1. **GPU not used:**
   ```bash
   # Check PyTorch CUDA
   python -c "import torch; print(torch.cuda.is_available())"
   ```

2. **Model download errors:**
   - First run downloads CRAFT and PARSEQ models
   - Models stored in `~/.cache/huggingface/`
   - Requires ~200MB download

3. **Out of memory:**
   - Reduce batch size
   - Use CPU mode (automatic fallback)
   - Close other GPU applications

---

## Performance Tips

### For Maximum Speed:
1. **Use GPU** - 5-10x faster than CPU
2. **Batch Processing** - Process multiple folders at once
3. **Limit Processing** - Use `--limit N` for testing
4. **Preload Models** - First run slower due to downloads

### For Maximum Accuracy:
1. **High-quality images** - 300 DPI or higher
2. **Good lighting** - Clear contrast
3. **Straight text** - Minimal rotation
4. **PaddleOCR** - Generally more accurate for documents

---

## Example Workflow

### Complete Processing Pipeline:

```bash
# 1. Check GPU status
python ocr_processor_paddle_tamil.py --check-gpu

# 2. Test with limited folders
python ocr_processor_paddle_tamil.py --languages ta en --limit 2 --verbose

# 3. Process all folders
python ocr_processor_paddle_tamil.py --languages ta en

# 4. Compare with ocr-tamil
python ocr_processor_tamil_native.py --limit 2

# 5. Review outputs
ls md-files-paddle-tamil/
ls md-files-tamil-native/
```

---

## Output Directories

- **PaddleOCR:** `md-files-paddle-tamil/`
- **ocr-tamil:** `md-files-tamil-native/`
- **Tesseract:** `md-files-tesseract/`
- **Surya:** `md-files-surya/` (if available)
- **CPU:** `md-files-cpu/`

Each directory contains markdown files with extracted text from the PDFs.
