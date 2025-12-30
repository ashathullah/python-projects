"""
Performance Comparison Script for OCR Methods

Compares the performance of:
1. EasyOCR with GPU
2. EasyOCR with CPU only
3. Tesseract OCR

Usage:
  python compare_ocr_performance.py --limit 1 --languages en
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_script(script_name: str, languages: str, limit: int, is_tesseract: bool = False) -> None:
    """Run an OCR script and display results."""
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f"[ERROR] Script not found: {script_path}")
        return
    
    print("\n" + "=" * 80)
    print(f"Running: {script_name}")
    print("=" * 80 + "\n")
    
    # Build command
    cmd = [sys.executable, str(script_path), "--limit", str(limit)]
    
    if is_tesseract:
        # Tesseract uses different language format
        cmd.extend(["--languages", languages])
    else:
        # EasyOCR uses space-separated languages
        lang_list = languages.replace("+", " ").split()
        cmd.extend(["--languages"] + lang_list)
    
    # Run the script
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Script failed with exit code {e.returncode}")
    except KeyboardInterrupt:
        print("\n[INFO] Script interrupted by user")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare OCR performance across different methods."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Process only first N folders (0 = all)."
    )
    parser.add_argument(
        "--languages",
        type=str,
        default="en ta",
        help="Languages for OCR. For EasyOCR: 'en ta'. For Tesseract: 'eng+tam'."
    )
    parser.add_argument(
        "--skip-gpu",
        action="store_true",
        help="Skip GPU-accelerated EasyOCR test."
    )
    parser.add_argument(
        "--skip-cpu",
        action="store_true",
        help="Skip CPU-only EasyOCR test."
    )
    parser.add_argument(
        "--skip-tesseract",
        action="store_true",
        help="Skip Tesseract OCR test."
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("OCR PERFORMANCE COMPARISON")
    print("=" * 80)
    print(f"Folders to process: {args.limit if args.limit > 0 else 'all'}")
    print(f"Languages: {args.languages}")
    print()
    
    # Run each script
    if not args.skip_gpu:
        run_script("ocr_processor.py", args.languages, args.limit)
    
    if not args.skip_cpu:
        run_script("ocr_processor_cpu.py", args.languages, args.limit)
    
    if not args.skip_tesseract:
        # Convert language format for Tesseract (en -> eng, ta -> tam, hi -> hin)
        tess_langs = (args.languages
                     .replace("en", "eng")
                     .replace("ta", "tam")
                     .replace("hi", "hin")
                     .replace("te", "tel")
                     .replace("ka", "kan")
                     .replace("mr", "mar")
                     .replace(" ", "+"))
        run_script("ocr_processor_tesseract.py", tess_langs, args.limit, is_tesseract=True)
    
    print("\n" + "=" * 80)
    print("COMPARISON COMPLETE")
    print("=" * 80)
    print("\nCheck the following directories for results:")
    print("  - md-files/         (GPU EasyOCR)")
    print("  - md-files-cpu/     (CPU EasyOCR)")
    print("  - md-files-tesseract/ (Tesseract)")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
