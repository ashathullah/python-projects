"""
OCR Processor using ocr-tamil library (specialized Tamil OCR with GPU acceleration).

Uses ocr-tamil library which is specifically fine-tuned for Tamil language text.
Based on PARSEQ and CRAFT models, excellent for scene text and document OCR.
Processes images from extracted PDFs and generates markdown files.

Installation:
  pip install ocr-tamil
  
  Note: Requires PyTorch with CUDA support for GPU acceleration.
  For GPU support, install PyTorch with CUDA:
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

Defaults:
  - Input:    pdf-converter/extracted/*/images/*.png
  - Output:   pdf-converter/md-files-tamil-native/<pdf-stem>.md

Examples:
  python ocr_processor_tamil_native.py
  python ocr_processor_tamil_native.py --limit 2
  python ocr_processor_tamil_native.py --check-gpu
  python ocr_processor_tamil_native.py --no-detection

Note: This library is specifically optimized for Tamil text recognition.
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

try:
    from ocr_tamil.ocr import OCR
    OCR_TAMIL_AVAILABLE = True
except ImportError:
    OCR_TAMIL_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None


def check_gpu_status() -> None:
    """Check and display GPU status for PyTorch/ocr-tamil."""
    if not TORCH_AVAILABLE:
        print("[ERROR] PyTorch not installed")
        return
    
    print("\n" + "=" * 60)
    print("GPU STATUS CHECK (PyTorch/ocr-tamil)")
    print("=" * 60)
    
    # Check CUDA availability
    cuda_available = torch.cuda.is_available()
    print(f"PyTorch CUDA Available: {cuda_available}")
    
    if cuda_available:
        print(f"CUDA Version: {torch.version.cuda}")
        print(f"cuDNN Version: {torch.backends.cudnn.version()}")
        print(f"Number of GPUs: {torch.cuda.device_count()}")
        
        for i in range(torch.cuda.device_count()):
            print(f"\nGPU {i}:")
            print(f"  Name: {torch.cuda.get_device_name(i)}")
            print(f"  Compute Capability: {torch.cuda.get_device_capability(i)}")
            
            # Get memory info
            mem_total = torch.cuda.get_device_properties(i).total_memory / (1024**3)
            mem_reserved = torch.cuda.memory_reserved(i) / (1024**3)
            mem_allocated = torch.cuda.memory_allocated(i) / (1024**3)
            
            print(f"  Total Memory: {mem_total:.2f} GB")
            print(f"  Reserved Memory: {mem_reserved:.2f} GB")
            print(f"  Allocated Memory: {mem_allocated:.2f} GB")
    else:
        print("[INFO] CUDA not available, will use CPU")
        # Check if MPS is available (Apple Silicon)
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            print("[INFO] MPS (Apple Silicon GPU) is available")
    
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


def _initialize_ocr_reader(use_detection: bool = True) -> tuple[Any, str]:
    """Initialize ocr-tamil reader with automatic GPU detection."""
    if not OCR_TAMIL_AVAILABLE:
        print("[ERROR] ocr-tamil not installed. Please run:")
        print("  pip install ocr-tamil")
        raise ImportError("ocr-tamil is required but not installed")
    
    if not TORCH_AVAILABLE:
        print("[WARNING] PyTorch not installed. OCR may not work correctly.")
        print("  Please install: pip install torch torchvision")
    
    # Determine device
    device = "cpu"
    if TORCH_AVAILABLE:
        if torch.cuda.is_available():
            device = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            print(f"[INFO] GPU detected: {gpu_name}")
            print(f"[INFO] CUDA version: {torch.version.cuda}")
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = "mps"
            print("[INFO] Apple Silicon GPU (MPS) detected")
        else:
            print("[INFO] No GPU detected, using CPU")
    
    print(f"[INFO] Initializing ocr-tamil library...")
    print(f"[INFO] Mode: {device.upper()}")
    print(f"[INFO] Text detection: {'Enabled (CRAFT model)' if use_detection else 'Disabled'}")
    
    try:
        # Initialize OCR
        # detect=True enables text detection + recognition (CRAFT + PARSEQ)
        # If GPU is available, PyTorch will automatically use it
        ocr = OCR(detect=use_detection)
        
        print(f"[SUCCESS] ocr-tamil initialized ({device.upper()} mode)")
        if use_detection:
            print("[INFO] Using CRAFT for text detection + PARSEQ for recognition")
        else:
            print("[INFO] Using PARSEQ for recognition only (assume full image is text)")
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize ocr-tamil: {e}")
        print("[INFO] First run may download model files automatically.")
        raise
    
    return ocr, device


def _process_image_with_ocr(ocr: Any, image_path: Path) -> tuple[str, float]:
    """Process a single image with OCR and return extracted text and processing time."""
    try:
        start_time = time.time()
        
        # ocr-tamil returns a list of lists (one per detected text region)
        # Each inner list contains words from that region
        result = ocr.predict(str(image_path))
        processing_time = time.time() - start_time
        
        # Extract and format text
        # result is a list of lists: [[word1, word2], [word3, word4], ...]
        text_lines = []
        if result:
            for text_region in result:
                if text_region:
                    # Join words in each region with spaces
                    line_text = " ".join(text_region)
                    text_lines.append(line_text)
        
        text = "\n".join(text_lines) if text_lines else "[No text detected]"
        return text.strip(), processing_time
        
    except Exception as e:
        print(f"  [WARNING] Error processing {image_path.name}: {e}")
        return f"[Error processing image: {e}]", 0.0


def _process_folder(
    folder: Path,
    ocr: Any,
    md_output_dir: Path,
    device: str
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
    device_tag = f"[{device.upper()}]"
    
    # Process each image
    md_content = []
    md_content.append(f"# {folder_name}\n")
    md_content.append(f"Extracted from PDF with {len(images)} pages\n")
    md_content.append(f"OCR Method: ocr-tamil (PARSEQ + CRAFT) {device_tag}\n")
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
    default_md_output = script_dir / "md-files-tamil-native"
    
    parser = argparse.ArgumentParser(
        description="Process extracted PDF images with ocr-tamil (specialized Tamil OCR, GPU-accelerated).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ocr_processor_tamil_native.py
  python ocr_processor_tamil_native.py --limit 2
  python ocr_processor_tamil_native.py --check-gpu
  python ocr_processor_tamil_native.py --no-detection

Notes:
  - This library is specifically optimized for Tamil text
  - Uses CRAFT model for text detection and PARSEQ for recognition
  - Automatically uses GPU if PyTorch with CUDA is available
  - First run will download model files (may take a few minutes)
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
        "--limit",
        type=int,
        default=0,
        help="Process only first N folders (0 = all)."
    )
    parser.add_argument(
        "--no-detection",
        action="store_true",
        help="Disable text detection (assumes entire image is text)."
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
    use_detection = not args.no_detection
    ocr, device = _initialize_ocr_reader(use_detection)
    init_time = time.time() - init_start
    print(f"[TIMING] Initialization took: {init_time:.2f}s")
    
    # Process each folder
    results = []
    total_start = time.time()
    for folder in folders:
        result = _process_folder(folder, ocr, md_output_dir, device)
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
    print(f"[INFO] Processing device: {device.upper()}")
    print(f"[INFO] OCR library: ocr-tamil (PARSEQ + CRAFT)")
    print(f"[TIMING] Initialization: {init_time:.2f}s")
    print(f"[TIMING] OCR Processing: {total_ocr_time:.2f}s")
    print(f"[TIMING] Total elapsed: {total_elapsed:.2f}s")
    if total_images > 0:
        print(f"[TIMING] Average per image: {total_ocr_time/total_images:.2f}s")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
