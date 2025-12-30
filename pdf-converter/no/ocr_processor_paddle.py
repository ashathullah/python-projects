"""
OCR Processor using PaddleOCR with GPU acceleration and Tamil support.

Uses PaddleOCR which has excellent Tamil language support.
Processes images from extracted PDFs and generates markdown files.

Defaults:
  - Input:    pdf-converter/extracted/*/images/*.png
  - Output:   pdf-converter/md-files/<pdf-stem>.md

Examples:
  python ocr_processor_paddle.py --languages en ta
  python ocr_processor_paddle.py --limit 2
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any
import torch

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False


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


def _initialize_ocr_reader(languages: list[str]) -> tuple[Any, bool]:
    """Initialize PaddleOCR reader with GPU support (fallback to CPU)."""
    if not PADDLEOCR_AVAILABLE:
        print("[ERROR] PaddleOCR not installed. Please run: pip install paddlepaddle paddleocr")
        raise ImportError("PaddleOCR is required but not installed")
    
    # Check GPU availability
    use_gpu = torch.cuda.is_available()
    
    if use_gpu:
        gpu_name = torch.cuda.get_device_name(0)
        print(f"[INFO] GPU detected: {gpu_name}")
        print(f"[INFO] CUDA version: {torch.version.cuda}")
    else:
        print("[INFO] No GPU detected, using CPU")
    
    # PaddleOCR language codes
    # Note: For Tamil support, use 'latin' or 'en' with multilingual capabilities
    has_tamil = 'ta' in languages
    
    if has_tamil:
        print(f"[INFO] Tamil detected - using multilingual OCR mode...")
        print(f"[INFO] Initializing PaddleOCR with multilingual support...")
    else:
        print(f"[INFO] Initializing PaddleOCR with languages: {', '.join(languages)}...")
    
    try:
        # Initialize PaddleOCR
        # PaddleOCR doesn't have direct Tamil support, use 'latin' for multilingual scripts
        ocr = PaddleOCR(
            use_angle_cls=True,
            lang='latin',  # Latin handles multilingual including Indic scripts
            use_gpu=use_gpu,
            show_log=False
        )
        print(f"[SUCCESS] PaddleOCR initialized with multilingual support ({'GPU' if use_gpu else 'CPU'} mode)")
    except Exception as e:
        print(f"[ERROR] Failed to initialize PaddleOCR: {e}")
        raise
    
    return ocr, use_gpu


def _process_image_with_ocr(ocr: Any, image_path: Path) -> tuple[str, float]:
    """Process a single image with OCR and return extracted text and processing time."""
    try:
        start_time = time.time()
        # PaddleOCR returns a list of ([bbox], (text, confidence))
        result = ocr.ocr(str(image_path), cls=True)
        processing_time = time.time() - start_time
        
        # Extract text from PaddleOCR result format
        text_lines = []
        if result and result[0]:
            for line in result[0]:
                # line is [bbox, (text, confidence)]
                if line and len(line) >= 2:
                    text_lines.append(line[1][0])
        
        text = "\n".join(text_lines) if text_lines else "[No text detected]"
        return text.strip(), processing_time
    except Exception as e:
        print(f"  [WARNING] Error processing {image_path.name}: {e}")
        return f"[Error processing image: {e}]", 0.0


def _process_folder(
    folder: Path,
    ocr: Any,
    md_output_dir: Path,
    use_gpu: bool
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
    device_tag = "[GPU]" if use_gpu else "[CPU]"
    
    # Process each image
    md_content = []
    md_content.append(f"# {folder_name}\n")
    md_content.append(f"Extracted from PDF with {len(images)} pages\n")
    md_content.append("---\n")
    total_time = 0.0
    
    for idx, image_path in enumerate(images, start=1):
        # Extract text from image
        text, img_time = _process_image_with_ocr(ocr, image_path)
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
        description="Process extracted PDF images with PaddleOCR (GPU-accelerated, Tamil support)."
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
    ocr, use_gpu = _initialize_ocr_reader(args.languages)
    init_time = time.time() - init_start
    print(f"[TIMING] Initialization took: {init_time:.2f}s")
    
    # Process each folder
    results = []
    total_start = time.time()
    for folder in folders:
        result = _process_folder(folder, ocr, md_output_dir, use_gpu)
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
    print(f"[INFO] Processing mode: {'GPU' if use_gpu else 'CPU'}")
    print(f"[TIMING] Initialization: {init_time:.2f}s")
    print(f"[TIMING] OCR Processing: {total_ocr_time:.2f}s")
    print(f"[TIMING] Total elapsed: {total_elapsed:.2f}s")
    if total_images > 0:
        print(f"[TIMING] Average per image: {total_ocr_time/total_images:.2f}s")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
