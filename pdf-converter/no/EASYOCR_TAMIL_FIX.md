# EasyOCR Tamil Language Fix

## Problem

When loading Tamil language in EasyOCR, you may encounter this error:

```python
import easyocr
reader = easyocr.Reader(['ta'])
```

**Error:**
```
RuntimeError: Error(s) in loading state_dict for Model:
size mismatch for Prediction.weight: copying a param with shape torch.Size([143, 512]) 
from checkpoint, the shape in current model is torch.Size([127, 512]).
size mismatch for Prediction.bias: copying a param with shape torch.Size([143]) 
from checkpoint, the shape in current model is torch.Size([127]).
```

## Root Cause

The EasyOCR Tamil model checkpoint contains 143 characters, but the model configuration (ta.yaml) 
specifies only 127 characters. This mismatch causes the model loading to fail.

## Solution

The fix involves updating the character list in the Tamil model configuration file:

### Method 1: Automated Fix (Recommended)

1. First, try to initialize EasyOCR with Tamil to download the model:
   ```bash
   python -c "import easyocr; easyocr.Reader(['ta'])"
   ```
   
   This will fail but will download the necessary model files.

2. Run the fix script:
   ```bash
   python fix_easyocr_tamil.py
   ```

3. The script will:
   - Locate the EasyOCR model directory (`~/.EasyOCR/model/`)
   - Find the `opt.txt` file with the complete character list
   - Update or create `~/.EasyOCR/user_network/ta.yaml` with the correct characters
   - Backup the original file before making changes

### Method 2: Manual Fix

1. **Download the Tamil model** (if not already done):
   ```bash
   python -c "import easyocr; easyocr.Reader(['ta'])"
   ```

2. **Locate the files**:
   - Windows: `C:\Users\<username>\.EasyOCR\model\`
   - Linux/Mac: `~/.EasyOCR/model/`

3. **Find opt.txt**:
   - Look for `opt.txt` in a subdirectory under the model folder
   - This file contains the complete character list (143 characters)

4. **Extract the character list**:
   - Open `opt.txt` and find the line starting with `character:`
   - Copy the entire character string after the colon

5. **Update ta.yaml**:
   - Create or edit `~/.EasyOCR/user_network/ta.yaml`
   - Add or replace the character line:
     ```yaml
     character: [paste the character string from opt.txt here]
     ```

6. **Test**:
   ```python
   import easyocr
   reader = easyocr.Reader(['ta'])
   print("Tamil model loaded successfully!")
   ```

## Alternative: Use Tesseract (Current Implementation)

This project already uses Tesseract OCR as a fallback for Tamil, which has excellent Tamil support:

```bash
# Install Tesseract with Tamil language pack
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-tam

# Use the Tesseract processor
python ocr_processor_tesseract.py --languages eng+tam
```

## Files in This Project

- **fix_easyocr_tamil.py** - Automated fix script for EasyOCR Tamil issue
- **ocr_processor_tesseract.py** - Uses Tesseract (recommended for Tamil)
- **ocr_processor.py** - Falls back to Tesseract when Tamil is detected
- **ocr_processor_cpu.py** - EasyOCR with CPU (skips Tamil on error)

## References

- [EasyOCR GitHub Issue](https://github.com/JaidedAI/EasyOCR/issues)
- [EasyOCR Documentation](https://github.com/JaidedAI/EasyOCR)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)

## Testing

After applying the fix, test with:

```python
import easyocr

# Test Tamil
reader = easyocr.Reader(['ta'])
text = reader.readtext('tamil_image.png')
print(text)

# Test English + Tamil
reader = easyocr.Reader(['en', 'ta'])
text = reader.readtext('bilingual_image.png')
print(text)
```
