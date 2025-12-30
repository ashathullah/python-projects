"""
OCR Processor for extracted PDF images with GPU acceleration.

Uses PaddleOCR with GPU support (falls back to CPU if GPU unavailable).
Processes images from extracted PDFs and generates markdown files.

Defaults:
  - Input:    pdf-converter/extracted/*/images/*.png
  - Output:   pdf-converter/md-files/<pdf-stem>.md

Examples:
  python pdf-converter/ocr_processor.py
  python pdf-converter/ocr_processor.py --languages en ta
  python pdf-converter/ocr_processor.py --limit 2
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any
import torch

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


def _get_extracted_folders(extracted_dir: Path) -> list[Path]:
    """Get all folders in extracted directory that contain images."""
    folders = []
    for folder in sorted(extracted_dir.iterdir()):
        if folder.is_dir():
            images_dir = folder / "images"
            if images_dir.exists() and images_dir.is_dir():
                folders.append(folder)
    return folders


def _get_sorted_images(images_dir: Path) -> list[Path]:
    """Get all images from a directory, sorted by name."""
    extensions = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
    images = [
        img for img in images_dir.iterdir()
        if img.is_file() and img.suffix.lower() in extensions
    ]
    return sorted(images)


def _initialize_ocr_reader(languages: list[str]) -> tuple[Any, bool, str]:
    """Initialize OCR reader (EasyOCR with fallback to Tesseract for Tamil)."""
    # Check GPU availability
    use_gpu = torch.cuda.is_available()
    
    if use_gpu:
        gpu_name = torch.cuda.get_device_name(0)
        print(f"[INFO] GPU detected: {gpu_name}")
        print(f"[INFO] CUDA version: {torch.version.cuda}")
    else:
        print("[INFO] No GPU detected, using CPU")
    
    # Check if Tamil is requested
    has_tamil = 'ta' in languages
    
    if has_tamil and TESSERACT_AVAILABLE:
        # Use Tesseract for Tamil support
        print(f"[INFO] Tamil detected - using Tesseract OCR (better Tamil support)")
        
        # Set Tesseract path for Windows
        if os.name == 'nt':
            tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if Path(tesseract_path).exists():
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        # Map to Tesseract language codes
        lang_map = {"en": "eng", "ta": "tam", "hi": "hin", "te": "tel", "ka": "kan", "mr": "mar"}
        tesseract_langs = "+".join([lang_map.get(lang, lang) for lang in languages])
        
        try:
            version = pytesseract.get_tesseract_version()
            print(f"[INFO] Tesseract version: {version}")
            print(f"[INFO] Languages: {tesseract_langs}")
            print(f"[SUCCESS] Tesseract OCR initialized (CPU mode)")
            return tesseract_langs, False, "tesseract"
        except Exception as e:
            print(f"[WARNING] Tesseract not available: {e}")
            print(f"[INFO] Falling back to EasyOCR without Tamil...")
            # Remove Tamil and try EasyOCR with remaining languages
            languages = [lang for lang in languages if lang != 'ta']
            if not languages:
                languages = ['en']
    
    # Use EasyOCR
    if not EASYOCR_AVAILABLE:
        print("[ERROR] EasyOCR not installed. Please run: pip install easyocr")
        raise ImportError("EasyOCR is required but not installed")
    
    # Map language codes for EasyOCR
    lang_map = {"en": "en", "ta": "ta", "hi": "hi", "te": "te", "ka": "kn", "mr": "mr"}
    easyocr_langs = [lang_map.get(lang, lang) for lang in languages]
    
    print(f"[INFO] Initializing EasyOCR with languages: {', '.join(easyocr_langs)}...")
    
    try:
        reader = easyocr.Reader(easyocr_langs, gpu=use_gpu)
        print(f"[SUCCESS] EasyOCR initialized ({'GPU' if use_gpu else 'CPU'} mode)")
        return reader, use_gpu, "easyocr"
    except RuntimeError as e:
        if 'ta' in easyocr_langs:
            print(f"[WARNING] Tamil model has compatibility issues")
            print(f"[INFO] Please use: python ocr_processor_tesseract.py --languages eng+tam")
        raise
    
    return reader, use_gpu, "easyocr"


def _process_image_with_ocr(reader: Any, image_path: Path, ocr_engine: str) -> tuple[str, float]:
    """Process a single image with OCR and return extracted text and processing time."""
    try:
        start_time = time.time()
        
        if ocr_engine == "tesseract":
            # Use Tesseract (reader is the language string)
            img = Image.open(image_path)
            result = pytesseract.image_to_string(img, lang=reader)
            img.close()
            text = result.strip() if result.strip() else "[No text detected]"
        else:
            # Use EasyOCR (reader is the EasyOCR object)
            result = reader.readtext(str(image_path))
            text_lines = []
            if result:
                for detection in result:
                    if len(detection) >= 2:
                        text_lines.append(detection[1])
            text = "\n".join(text_lines) if text_lines else "[No text detected]"
        
        processing_time = time.time() - start_time
        return text.strip(), processing_time
    except Exception as e:
        print(f"  [WARNING] Error processing {image_path.name}: {e}")
        return f"[Error processing image: {e}]", 0.0


def _process_folder(
    folder: Path,
    reader: Any,
    md_output_dir: Path,
    use_gpu: bool,
    ocr_engine: str
) -> dict[str, Any]:
    """Process all images in a folder and create a markdown file."""
    folder_name = folder.name
    images_dir = folder / "images"
    
    print(f"\nProcessing: {folder_name}")
    
    # Get sorted images
    images = _get_sorted_images(images_dir)
    if not images:
        print(f"  [WARNING] No images found in {images_dir}")
        return {"folder": folder_name, "images_processed": 0, "error": "No images found"}
    
    print(f"  Found {len(images)} images")
    
    # Set device tag
    if ocr_engine == "tesseract":
        device_tag = "[TESSERACT]"
    else:
        device_tag = "[GPU]" if use_gpu else "[CPU]"
    
    # Process each image
    md_content = []
    md_content.append(f"# {folder_name}\n")
    md_content.append(f"Extracted from PDF with {len(images)} pages\n")
    md_content.append("---\n")
    total_time = 0.0
    
    for idx, image_path in enumerate(images, start=1):
        # Extract text from image
        text, img_time = _process_image_with_ocr(reader, image_path, ocr_engine)
        total_time += img_time
        print(f"  [{idx}/{len(images)}] {image_path.name} {device_tag} - {img_time:.2f}s")
        
        # Add page header
        md_content.append(f"\n## Page {idx}\n")
        md_content.append(f"*Source: {image_path.name}*\n")
        md_content.append(text)
        md_content.append("\n---\n")
    
    # Write markdown file
    md_output_dir.mkdir(parents=True, exist_ok=True)
    output_path = md_output_dir / f"{folder_name}.md"
    output_path.write_text("\n".join(md_content), encoding="utf-8")
    avg_time = total_time / len(images) if images else 0
    print(f"  [SUCCESS] Saved to: {output_path.name}")
    print(f"  [TIMING] Total: {total_time:.2f}s | Avg per image: {avg_time:.2f}s")
    
    return {
        "folder": folder_name,
        "images_processed": len(images),
        "output_path": str(output_path.as_posix()),
        "total_time": total_time,
        "avg_time": avg_time
    }


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    default_extracted = script_dir / "extracted"
    default_md_output = script_dir / "md-files"
    
    parser = argparse.ArgumentParser(
        description="Process extracted PDF images with EasyOCR (GPU-accelerated)."
    )
    parser.add_argument(
        "--extracted",
        type=Path,
        default=default_extracted,
        help="Directory containing extracted image folders."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_md_output,
        help="Output directory for markdown files."
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["en"],
        help="Languages for OCR (e.g., en ta hi). Use 'en' for English, 'ta' for Tamil."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only first N folders (0 = all)."
    )
    
    args = parser.parse_args()
    
    extracted_dir: Path = args.extracted
    md_output_dir: Path = args.output
    
    if not extracted_dir.exists():
        print(f"[ERROR] Extracted directory not found: {extracted_dir}")
        return 1
    
    # Get all folders to process
    folders = _get_extracted_folders(extracted_dir)
    if args.limit and args.limit > 0:
        folders = folders[:args.limit]
    
    if not folders:
        print(f"[ERROR] No folders with images found in: {extracted_dir}")
        return 2
    
    init_start = time.time()
    reader, use_gpu, ocr_engine = _initialize_ocr_reader(args.languages)
    init_time = time.time() - init_start
    print(f"[TIMING] Initialization took: {init_time:.2f}s")
    
    # Process each folder
    results = []
    total_start = time.time()
    for folder in folders:
        result = _process_folder(folder, reader, md_output_dir, use_gpu, ocr_engine)
        results.append(result)
    total_elapsed = time.time() - total_start
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_images = sum(r.get("images_processed", 0) for r in results)
    total_ocr_time = sum(r.get("total_time", 0) for r in results)
    successful = len([r for r in results if r.get("images_processed", 0) > 0])
    print(f"[SUCCESS] Processed {successful}/{len(folders)} folders")
    print(f"[SUCCESS] Total images processed: {total_images}")
    print(f"[SUCCESS] Output directory: {md_output_dir}")
    engine_name = "Tesseract (CPU)" if ocr_engine == "tesseract" else f"EasyOCR ({'GPU' if use_gpu else 'CPU'})"
    print(f"[INFO] Processing mode: {engine_name}")
    print(f"[TIMING] Initialization: {init_time:.2f}s")
    print(f"[TIMING] OCR Processing: {total_ocr_time:.2f}s")
    print(f"[TIMING] Total elapsed: {total_elapsed:.2f}s")
    if total_images > 0:
        print(f"[TIMING] Average per image: {total_ocr_time/total_images:.2f}s")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
