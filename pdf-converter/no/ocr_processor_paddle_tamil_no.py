"""
OCR Processor using PaddleOCR with Enhanced Tamil Support (GPU-accelerated).

Uses PaddleOCR with Tamil language model for high-accuracy OCR.
Processes images from extracted PDFs and generates markdown files.

Installation:
  # Install PaddlePaddle GPU (Ensure you have CUDA/cuDNN installed)
  python -m pip install paddlepaddle-gpu
  # Install PaddleOCR toolkit
  pip install paddleocr

Defaults:
  - Input:    pdf-converter/extracted/*/images/*.png
  - Output:   pdf-converter/md-files-paddle-tamil/<pdf-stem>.md

Examples:
  python ocr_processor_paddle_tamil.py
  python ocr_processor_paddle_tamil.py --languages ta en
  python ocr_processor_paddle_tamil.py --limit 2
  python ocr_processor_paddle_tamil.py --check-gpu

Note: This script uses PaddleOCR's 'ta' language model for Tamil text.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

try:
    from paddleocr import PaddleOCR
    import paddle
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    paddle = None


def check_gpu_status() -> None:
    """Check and display GPU status for PaddleOCR."""
    if paddle is None:
        print("[ERROR] PaddlePaddle not installed")
        return
    
    print("\n" + "=" * 60)
    print("GPU STATUS CHECK (PaddleOCR)")
    print("=" * 60)
    
    # Check if Paddle is compiled with CUDA
    cuda_compiled = paddle.is_compiled_with_cuda()
    print(f"PaddlePaddle compiled with CUDA: {cuda_compiled}")
    
    if cuda_compiled:
        try:
            # Get CUDA device count
            device_count = paddle.device.cuda.device_count()
            print(f"CUDA Devices Available: {device_count}")
            
            if device_count > 0:
                # Get device properties
                for i in range(device_count):
                    print(f"\nDevice {i}:")
                    print(f"  Name: {paddle.device.cuda.get_device_name(i)}")
                    print(f"  Capability: {paddle.device.cuda.get_device_capability(i)}")
        except Exception as e:
            print(f"Error getting CUDA device info: {e}")
    else:
        print("[INFO] PaddlePaddle is not using CUDA")
    
    # Check ROCm (for AMD GPUs)
    rocm_compiled = paddle.device.is_compiled_with_rocm()
    if rocm_compiled:
        print(f"\nPaddlePaddle compiled with ROCm (AMD GPU): {rocm_compiled}")
    
    print("=" * 60 + "\n")


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
    """Initialize PaddleOCR reader with GPU support and Tamil language model."""
    if not PADDLEOCR_AVAILABLE:
        print("[ERROR] PaddleOCR not installed. Please run:")
        print("  python -m pip install paddlepaddle-gpu")
        print("  pip install paddleocr")
        raise ImportError("PaddleOCR is required but not installed")
    
    # Check GPU availability
    use_gpu = paddle.is_compiled_with_cuda() if paddle else False
    
    if use_gpu:
        try:
            device_count = paddle.device.cuda.device_count()
            if device_count > 0:
                gpu_name = paddle.device.cuda.get_device_name(0)
                print(f"[INFO] GPU detected: {gpu_name}")
                print(f"[INFO] CUDA devices available: {device_count}")
            else:
                use_gpu = False
                print("[INFO] No CUDA devices available, using CPU")
        except Exception as e:
            use_gpu = False
            print(f"[WARNING] Error checking GPU: {e}")
            print("[INFO] Falling back to CPU")
    else:
        print("[INFO] PaddlePaddle not compiled with CUDA, using CPU")
    
    # Determine primary language
    # PaddleOCR supports 'ta' for Tamil directly
    primary_lang = languages[0] if languages else 'en'
    
    print(f"[INFO] Initializing PaddleOCR with primary language: {primary_lang}")
    print(f"[INFO] Mode: {'GPU' if use_gpu else 'CPU'}")
    
    try:
        # Initialize PaddleOCR with Tamil support
        # PaddleOCR 3.0+ uses device parameter instead of use_gpu
        device = 'gpu' if use_gpu else 'cpu'
        ocr = PaddleOCR(
            lang=primary_lang,        # Use 'ta' for Tamil, 'en' for English
            device=device,            # Use 'gpu' or 'cpu'
        )
        print(f"[SUCCESS] PaddleOCR initialized with '{primary_lang}' language model ({'GPU' if use_gpu else 'CPU'} mode)")
    except Exception as e:
        import traceback
        print(f"[ERROR] Failed to initialize PaddleOCR: {e}")
        print("[ERROR] Full traceback:")
        traceback.print_exc()
        print("[INFO] If you see language model download errors, PaddleOCR will automatically download the required models.")
        raise
    
    return ocr, use_gpu


def _process_image_with_ocr(ocr: Any, image_path: Path) -> tuple[str, float, dict]:
    """Process a single image with OCR and return extracted text, processing time, and stats."""
    try:
        start_time = time.time()
        # PaddleOCR returns a list of ([bbox], (text, confidence))
        result = ocr.ocr(str(image_path), cls=True)
        processing_time = time.time() - start_time
        
        # Extract text from PaddleOCR result format
        text_lines = []
        confidences = []
        
        if result and result[0]:
            for line in result[0]:
                # line is [bbox, (text, confidence)]
                if line and len(line) >= 2:
                    text, confidence = line[1]
                    text_lines.append(text)
                    confidences.append(confidence)
        
        text = "\n".join(text_lines) if text_lines else "[No text detected]"
        
        # Calculate stats
        stats = {
            "lines_detected": len(text_lines),
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "min_confidence": min(confidences) if confidences else 0.0,
            "max_confidence": max(confidences) if confidences else 0.0,
        }
        
        return text.strip(), processing_time, stats
    except Exception as e:
        print(f"  [WARNING] Error processing {image_path.name}: {e}")
        return f"[Error processing image: {e}]", 0.0, {}


def _process_folder(
    folder: Path,
    ocr: Any,
    md_output_dir: Path,
    use_gpu: bool,
    verbose: bool = False
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
    md_content.append(f"OCR Method: PaddleOCR (Tamil) {device_tag}\n")
    md_content.append("---\n")
    
    total_time = 0.0
    all_stats = []
    
    for idx, image_path in enumerate(images, start=1):
        # Extract text from image
        text, img_time, stats = _process_image_with_ocr(ocr, image_path)
        total_time += img_time
        all_stats.append(stats)
        
        if verbose and stats:
            print(f"  [{idx}/{len(images)}] {image_path.name} {device_tag} - {img_time:.2f}s "
                  f"(Lines: {stats.get('lines_detected', 0)}, Conf: {stats.get('avg_confidence', 0):.2f})")
        else:
            print(f"  [{idx}/{len(images)}] {image_path.name} {device_tag} - {img_time:.2f}s")
        
        # Add page header
        md_content.append(f"\n## Page {idx}\n")
        md_content.append(f"*Source: {image_path.name}*\n")
        if verbose and stats:
            md_content.append(f"*Lines detected: {stats.get('lines_detected', 0)}, "
                            f"Avg confidence: {stats.get('avg_confidence', 0):.2%}*\n")
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
        "avg_time": avg_time,
        "stats": all_stats
    }


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    default_extracted = script_dir / "extracted"
    default_md_output = script_dir / "md-files-paddle-tamil"
    
    parser = argparse.ArgumentParser(
        description="Process extracted PDF images with PaddleOCR (Tamil language support, GPU-accelerated).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ocr_processor_paddle_tamil.py
  python ocr_processor_paddle_tamil.py --languages ta en
  python ocr_processor_paddle_tamil.py --limit 2 --verbose
  python ocr_processor_paddle_tamil.py --check-gpu

Notes:
  - Use 'ta' for Tamil, 'en' for English
  - First run will download language models automatically
  - GPU acceleration requires CUDA-enabled PaddlePaddle installation
        """
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
        default=["ta"],
        help="Languages for OCR (e.g., ta en). Primary language will be used for the model."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only first N folders (0 = all)."
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed OCR statistics for each image."
    )
    parser.add_argument(
        "--check-gpu",
        action="store_true",
        help="Check GPU status and exit."
    )
    
    args = parser.parse_args()
    
    # Check GPU status if requested
    if args.check_gpu:
        check_gpu_status()
        return 0
    
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
    
    print(f"[INFO] Found {len(folders)} folder(s) to process")
    
    # Initialize OCR
    init_start = time.time()
    ocr, use_gpu = _initialize_ocr_reader(args.languages)
    init_time = time.time() - init_start
    print(f"[TIMING] Initialization took: {init_time:.2f}s")
    
    # Process each folder
    results = []
    total_start = time.time()
    for folder in folders:
        result = _process_folder(folder, ocr, md_output_dir, use_gpu, args.verbose)
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
    print(f"[INFO] Language model: {args.languages[0]}")
    print(f"[TIMING] Initialization: {init_time:.2f}s")
    print(f"[TIMING] OCR Processing: {total_ocr_time:.2f}s")
    print(f"[TIMING] Total elapsed: {total_elapsed:.2f}s")
    if total_images > 0:
        print(f"[TIMING] Average per image: {total_ocr_time/total_images:.2f}s")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
