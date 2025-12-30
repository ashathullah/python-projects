"""
OCR Processor using Surya OCR with GPU acceleration and Tamil support.

Uses Surya OCR which has excellent multilingual support including Tamil.
Processes images from extracted PDFs and generates markdown files.

Defaults:
  - Input:    pdf-converter/extracted/*/images/*.png
  - Output:   pdf-converter/md-files-surya/<pdf-stem>.md

Examples:
  python ocr_processor_surya.py --languages en ta
  python ocr_processor_surya.py --limit 2
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any
import torch

try:
    from surya.ocr import run_ocr
    from surya.model.detection.model import load_model as load_det_model, load_processor as load_det_processor
    from surya.model.recognition.model import load_model as load_rec_model
    from surya.model.recognition.processor import load_processor as load_rec_processor
    from PIL import Image
    SURYA_AVAILABLE = True
except ImportError:
    SURYA_AVAILABLE = False


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


def _initialize_surya_models(languages: list[str]) -> tuple[Any, Any, Any, Any, bool]:
    """Initialize Surya OCR models with GPU support."""
    if not SURYA_AVAILABLE:
        print("[ERROR] Surya OCR not installed. Please run: pip install surya-ocr")
        raise ImportError("Surya OCR is required but not installed")
    
    # Check GPU availability
    use_gpu = torch.cuda.is_available()
    
    if use_gpu:
        gpu_name = torch.cuda.get_device_name(0)
        print(f"[INFO] GPU detected: {gpu_name}")
        print(f"[INFO] CUDA version: {torch.version.cuda}")
    else:
        print("[INFO] No GPU detected, using CPU")
    
    # Map language codes for Surya
    # Surya uses full language names
    lang_map = {
        "en": "en",
        "ta": "ta",  # Tamil
        "hi": "hi",  # Hindi
        "te": "te",  # Telugu
        "ka": "kn",  # Kannada
        "mr": "mr"   # Marathi
    }
    surya_langs = [lang_map.get(lang, lang) for lang in languages]
    
    print(f"[INFO] Initializing Surya OCR with languages: {', '.join(surya_langs)}...")
    print(f"[INFO] Loading models (this may take a moment on first run)...")
    
    try:
        # Load detection and recognition models
        det_model = load_det_model()
        det_processor = load_det_processor()
        rec_model = load_rec_model()
        rec_processor = load_rec_processor()
        
        # Move models to GPU if available
        if use_gpu:
            det_model = det_model.cuda()
            rec_model = rec_model.cuda()
        
        print(f"[SUCCESS] Surya OCR initialized ({'GPU' if use_gpu else 'CPU'} mode)")
        return det_model, det_processor, rec_model, rec_processor, use_gpu
    except Exception as e:
        print(f"[ERROR] Failed to initialize Surya OCR: {e}")
        raise


def _process_image_with_surya(
    image_path: Path,
    det_model: Any,
    det_processor: Any,
    rec_model: Any,
    rec_processor: Any,
    languages: list[str]
) -> tuple[str, float]:
    """Process a single image with Surya OCR and return extracted text and processing time."""
    try:
        start_time = time.time()
        
        # Load image
        img = Image.open(image_path)
        
        # Run OCR
        predictions = run_ocr(
            [img],
            [languages],
            det_model,
            det_processor,
            rec_model,
            rec_processor
        )
        
        processing_time = time.time() - start_time
        
        # Extract text from predictions
        text_lines = []
        if predictions and len(predictions) > 0:
            pred = predictions[0]
            if hasattr(pred, 'text_lines'):
                for line in pred.text_lines:
                    if hasattr(line, 'text'):
                        text_lines.append(line.text)
        
        text = "\n".join(text_lines) if text_lines else "[No text detected]"
        
        # Clean up
        img.close()
        
        return text.strip(), processing_time
    except Exception as e:
        print(f"  [WARNING] Error processing {image_path.name}: {e}")
        return f"[Error processing image: {e}]", 0.0


def _process_folder(
    folder: Path,
    det_model: Any,
    det_processor: Any,
    rec_model: Any,
    rec_processor: Any,
    languages: list[str],
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
        text, img_time = _process_image_with_surya(
            image_path,
            det_model,
            det_processor,
            rec_model,
            rec_processor,
            languages
        )
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
    default_md_output = script_dir / "md-files-surya"
    
    parser = argparse.ArgumentParser(
        description="Process extracted PDF images with Surya OCR (GPU-accelerated, Tamil support)."
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
    languages: list[str] = args.languages
    
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
    det_model, det_processor, rec_model, rec_processor, use_gpu = _initialize_surya_models(languages)
    init_time = time.time() - init_start
    print(f"[TIMING] Initialization took: {init_time:.2f}s")
    
    # Process each folder
    results = []
    total_start = time.time()
    for folder in folders:
        result = _process_folder(
            folder,
            det_model,
            det_processor,
            rec_model,
            rec_processor,
            languages,
            md_output_dir,
            use_gpu
        )
        results.append(result)
    total_elapsed = time.time() - total_start
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY (SURYA OCR)")
    print("=" * 60)
    total_images = sum(r.get("images_processed", 0) for r in results)
    total_ocr_time = sum(r.get("total_time", 0) for r in results)
    successful = len([r for r in results if r.get("images_processed", 0) > 0])
    print(f"[SUCCESS] Processed {successful}/{len(folders)} folders")
    print(f"[SUCCESS] Total images processed: {total_images}")
    print(f"[SUCCESS] Output directory: {md_output_dir}")
    print(f"[INFO] Processing mode: Surya OCR ({'GPU' if use_gpu else 'CPU'})")
    print(f"[TIMING] Initialization: {init_time:.2f}s")
    print(f"[TIMING] OCR Processing: {total_ocr_time:.2f}s")
    print(f"[TIMING] Total elapsed: {total_elapsed:.2f}s")
    if total_images > 0:
        print(f"[TIMING] Average per image: {total_ocr_time/total_images:.2f}s")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
