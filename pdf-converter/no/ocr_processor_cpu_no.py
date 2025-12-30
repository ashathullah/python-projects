"""
OCR Processor for extracted PDF images with CPU-only processing.

Uses EasyOCR with CPU-only mode for performance comparison.
Processes images from extracted PDFs and generates markdown files.

Defaults:
  - Input:    pdf-converter/extracted/*/images/*.png
  - Output:   pdf-converter/md-files-cpu/<pdf-stem>.md

Examples:
  python pdf-converter/ocr_processor_cpu.py
  python pdf-converter/ocr_processor_cpu.py --languages en ta
  python pdf-converter/ocr_processor_cpu.py --limit 2
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


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


def _initialize_ocr_reader(languages: list[str]) -> Any:
    """Initialize EasyOCR reader with CPU-only mode."""
    if not EASYOCR_AVAILABLE:
        print("[ERROR] EasyOCR not installed. Please run: pip install easyocr")
        raise ImportError("EasyOCR is required but not installed")
    
    print("[INFO] Using CPU-only mode")
    
    # Map language codes for EasyOCR
    lang_map = {"en": "en", "ta": "ta", "hi": "hi", "te": "te", "ka": "kn", "mr": "mr"}
    easyocr_langs = [lang_map.get(lang, lang) for lang in languages]
    
    print(f"[INFO] Initializing EasyOCR with languages: {', '.join(easyocr_langs)}...")
    
    # Initialize EasyOCR with CPU-only (gpu=False)
    # Note: Tamil support may have model compatibility issues
    try:
        reader = easyocr.Reader(easyocr_langs, gpu=False)
    except RuntimeError as e:
        if 'ta' in easyocr_langs and 'size mismatch' in str(e):
            print(f"[WARNING] Tamil model has compatibility issues, using English only")
            easyocr_langs = ['en']
            reader = easyocr.Reader(easyocr_langs, gpu=False)
        else:
            raise
    
    print("[SUCCESS] EasyOCR initialized (CPU mode)")
    
    return reader


def _process_image_with_ocr(reader: Any, image_path: Path) -> tuple[str, float]:
    """Process a single image with OCR and return extracted text and processing time."""
    try:
        start_time = time.time()
        # EasyOCR returns a list of ([bbox], text, confidence)
        result = reader.readtext(str(image_path))
        processing_time = time.time() - start_time
        
        # Extract text from EasyOCR result format
        text_lines = []
        if result:
            for detection in result:
                # detection is ([bbox], text, confidence)
                if len(detection) >= 2:
                    text_lines.append(detection[1])
        
        text = "\n".join(text_lines) if text_lines else "[No text detected]"
        return text.strip(), processing_time
    except Exception as e:
        print(f"  [WARNING] Error processing {image_path.name}: {e}")
        return f"[Error processing image: {e}]", 0.0


def _process_folder(
    folder: Path,
    reader: Any,
    md_output_dir: Path
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
    
    # Process each image
    md_content = []
    md_content.append(f"# {folder_name}\n")
    md_content.append(f"Extracted from PDF with {len(images)} pages\n")
    md_content.append("---\n")
    
    total_time = 0.0
    
    for idx, image_path in enumerate(images, start=1):
        # Extract text from image
        text, img_time = _process_image_with_ocr(reader, image_path)
        total_time += img_time
        print(f"  [{idx}/{len(images)}] {image_path.name} [CPU] - {img_time:.2f}s")
        
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
    default_md_output = script_dir / "md-files-cpu"
    
    parser = argparse.ArgumentParser(
        description="Process extracted PDF images with EasyOCR (CPU-only)."
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
    
    print(f"Found {len(folders)} folder(s) to process")
    print(f"Languages: {', '.join(args.languages)}")
    
    # Initialize OCR reader with CPU-only
    print("\nInitializing OCR reader (CPU-only)...")
    init_start = time.time()
    reader = _initialize_ocr_reader(args.languages)
    init_time = time.time() - init_start
    print(f"[TIMING] Initialization took: {init_time:.2f}s")
    
    # Process each folder
    results = []
    total_start = time.time()
    for folder in folders:
        result = _process_folder(folder, reader, md_output_dir)
        results.append(result)
    total_elapsed = time.time() - total_start
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY (CPU-ONLY)")
    print("=" * 60)
    total_images = sum(r.get("images_processed", 0) for r in results)
    total_ocr_time = sum(r.get("total_time", 0) for r in results)
    successful = len([r for r in results if r.get("images_processed", 0) > 0])
    print(f"[SUCCESS] Processed {successful}/{len(folders)} folders")
    print(f"[SUCCESS] Total images processed: {total_images}")
    print(f"[SUCCESS] Output directory: {md_output_dir}")
    print(f"[INFO] Processing mode: CPU")
    print(f"[TIMING] Initialization: {init_time:.2f}s")
    print(f"[TIMING] OCR Processing: {total_ocr_time:.2f}s")
    print(f"[TIMING] Total elapsed: {total_elapsed:.2f}s")
    if total_images > 0:
        print(f"[TIMING] Average per image: {total_ocr_time/total_images:.2f}s")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
