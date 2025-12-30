"""
Quick test script to verify Tamil OCR implementations.

Tests both PaddleOCR and ocr-tamil libraries with GPU detection.

Usage:
  python test_tamil_ocr.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def test_paddleocr():
    """Test PaddleOCR with Tamil support."""
    print("\n" + "=" * 60)
    print("Testing PaddleOCR (Tamil)")
    print("=" * 60)
    
    try:
        from paddleocr import PaddleOCR
        import paddle
        
        print("[OK] PaddleOCR is installed")
        
        # Check CUDA
        cuda_available = paddle.is_compiled_with_cuda()
        print(f"[INFO] CUDA Support: {cuda_available}")
        
        if cuda_available:
            try:
                device_count = paddle.device.cuda.device_count()
                print(f"[INFO] CUDA Devices: {device_count}")
                if device_count > 0:
                    gpu_name = paddle.device.cuda.get_device_name(0)
                    print(f"[INFO] GPU: {gpu_name}")
            except Exception as e:
                print(f"[WARNING] Error checking GPU: {e}")
        
        # Try initializing OCR
        print("[INFO] Initializing PaddleOCR with Tamil language...")
        ocr = PaddleOCR(use_angle_cls=True, lang='ta', use_gpu=cuda_available, show_log=False)
        print("[SUCCESS] PaddleOCR initialized successfully!")
        
        return True
        
    except ImportError as e:
        print(f"[ERROR] PaddleOCR not installed: {e}")
        print("[INFO] Install with:")
        print("  python -m pip install paddlepaddle-gpu")
        print("  pip install paddleocr")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to initialize PaddleOCR: {e}")
        return False


def test_ocr_tamil():
    """Test ocr-tamil library."""
    print("\n" + "=" * 60)
    print("Testing ocr-tamil (Native Tamil OCR)")
    print("=" * 60)
    
    try:
        from ocr_tamil.ocr import OCR
        print("[OK] ocr-tamil is installed")
        
        # Check PyTorch
        try:
            import torch
            print(f"[OK] PyTorch is installed")
            
            cuda_available = torch.cuda.is_available()
            print(f"[INFO] CUDA Support: {cuda_available}")
            
            if cuda_available:
                print(f"[INFO] CUDA Version: {torch.version.cuda}")
                print(f"[INFO] GPU Count: {torch.cuda.device_count()}")
                if torch.cuda.device_count() > 0:
                    gpu_name = torch.cuda.get_device_name(0)
                    print(f"[INFO] GPU: {gpu_name}")
        except ImportError:
            print("[WARNING] PyTorch not installed - GPU acceleration not available")
        
        # Try initializing OCR
        print("[INFO] Initializing ocr-tamil...")
        ocr = OCR(detect=True)
        print("[SUCCESS] ocr-tamil initialized successfully!")
        
        return True
        
    except ImportError as e:
        print(f"[ERROR] ocr-tamil not installed: {e}")
        print("[INFO] Install with:")
        print("  pip install ocr-tamil")
        print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to initialize ocr-tamil: {e}")
        return False


def check_test_images():
    """Check if test images are available."""
    print("\n" + "=" * 60)
    print("Checking Test Images")
    print("=" * 60)
    
    script_dir = Path(__file__).resolve().parent
    extracted_dir = script_dir / "extracted"
    
    if not extracted_dir.exists():
        print(f"[WARNING] Extracted directory not found: {extracted_dir}")
        return False
    
    # Count folders with images
    folders_with_images = 0
    total_images = 0
    
    for folder in extracted_dir.iterdir():
        if folder.is_dir():
            images_dir = folder / "images"
            if images_dir.exists() and images_dir.is_dir():
                images = list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg"))
                if images:
                    folders_with_images += 1
                    total_images += len(images)
                    print(f"[OK] {folder.name}: {len(images)} images")
    
    print(f"\n[INFO] Found {folders_with_images} folders with {total_images} total images")
    
    if folders_with_images == 0:
        print("[WARNING] No test images found!")
        print("[INFO] Place PDF images in: extracted/*/images/*.png")
        return False
    
    return True


def main() -> int:
    """Main test function."""
    print("=" * 60)
    print("Tamil OCR Setup Verification")
    print("=" * 60)
    
    results = {
        "paddleocr": test_paddleocr(),
        "ocr_tamil": test_ocr_tamil(),
        "test_images": check_test_images()
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name:20s}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n[SUCCESS] All tests passed! You're ready to process Tamil OCR.")
        print("\nNext steps:")
        print("  1. Test PaddleOCR: python ocr_processor_paddle_tamil.py --limit 1")
        print("  2. Test ocr-tamil: python ocr_processor_tamil_native.py --limit 1")
    else:
        print("\n[WARNING] Some tests failed. Please install missing dependencies.")
        if not results["paddleocr"]:
            print("\nFor PaddleOCR:")
            print("  python -m pip install paddlepaddle-gpu")
            print("  pip install paddleocr")
        if not results["ocr_tamil"]:
            print("\nFor ocr-tamil:")
            print("  pip install ocr-tamil")
            print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
