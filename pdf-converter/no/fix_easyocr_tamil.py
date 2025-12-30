"""
Fix EasyOCR Tamil language model compatibility issue.

This script resolves the "size mismatch" error when loading Tamil ('ta') language
in EasyOCR by updating the character list in the model configuration file.

Issue: EasyOCR Tamil model checkpoint has 143 characters but expects 127.
Solution: Copy the complete character list from opt.txt to ta.yaml

Reference: https://github.com/JaidedAI/EasyOCR/issues

Usage:
    python fix_easyocr_tamil.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def get_easyocr_model_dir() -> Path:
    """Get the EasyOCR user network directory path."""
    # EasyOCR stores models in ~/.EasyOCR/model/
    home = Path.home()
    model_dir = home / ".EasyOCR" / "model"
    
    if not model_dir.exists():
        # Try alternate location
        model_dir = home / ".EasyOCR" / "user_network"
    
    return model_dir


def find_tamil_yaml(model_dir: Path) -> Path | None:
    """Find ta.yaml file in the model directory."""
    # Look for ta.yaml in common locations
    possible_paths = [
        model_dir / "ta.yaml",
        model_dir / "user_network" / "ta.yaml",
        Path.home() / ".EasyOCR" / "user_network" / "ta.yaml",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def find_opt_txt(model_dir: Path) -> Path | None:
    """Find opt.txt file containing the character list."""
    # Look for opt.txt in the model directory
    for path in model_dir.rglob("opt.txt"):
        return path
    
    # If not found, check if there's a downloaded Tamil model
    tamil_model_paths = list(model_dir.rglob("*tamil*")) + list(model_dir.rglob("*ta*"))
    for model_path in tamil_model_paths:
        if model_path.is_dir():
            opt_txt = model_path / "opt.txt"
            if opt_txt.exists():
                return opt_txt
    
    return None


def read_character_list(opt_txt_path: Path) -> str:
    """Read the character list from opt.txt file."""
    with open(opt_txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # The character list is typically on a line starting with "character:"
        for line in content.split('\n'):
            if line.strip().startswith('character:'):
                # Extract the character string (everything after "character:")
                char_list = line.split(':', 1)[1].strip()
                return char_list
    return ""


def update_tamil_yaml(yaml_path: Path, character_list: str) -> bool:
    """Update the ta.yaml file with the correct character list."""
    try:
        # Backup the original file
        backup_path = yaml_path.with_suffix('.yaml.bak')
        shutil.copy2(yaml_path, backup_path)
        print(f"[INFO] Created backup: {backup_path}")
        
        # Read the current YAML content
        with open(yaml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace the character line
        lines = content.split('\n')
        new_lines = []
        updated = False
        
        for line in lines:
            if line.strip().startswith('character:'):
                # Replace with the new character list
                new_lines.append(f"character: {character_list}")
                updated = True
                print(f"[INFO] Updated character list in {yaml_path}")
            else:
                new_lines.append(line)
        
        # If no character line found, add it
        if not updated:
            new_lines.append(f"character: {character_list}")
            print(f"[INFO] Added character list to {yaml_path}")
        
        # Write the updated content
        with open(yaml_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        
        return True
    
    except Exception as e:
        print(f"[ERROR] Failed to update {yaml_path}: {e}")
        return False


def create_tamil_yaml_from_scratch(yaml_path: Path, character_list: str) -> bool:
    """Create a new ta.yaml file if it doesn't exist."""
    try:
        # Create the directory if needed
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a basic YAML configuration
        yaml_content = f"""character: {character_list}
"""
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        print(f"[SUCCESS] Created {yaml_path}")
        return True
    
    except Exception as e:
        print(f"[ERROR] Failed to create {yaml_path}: {e}")
        return False


def main():
    """Main function to fix EasyOCR Tamil language model."""
    print("=" * 70)
    print("EasyOCR Tamil Language Model Fix")
    print("=" * 70)
    print()
    
    # Step 1: Find the EasyOCR model directory
    model_dir = get_easyocr_model_dir()
    print(f"[INFO] Looking for EasyOCR models in: {model_dir}")
    
    if not model_dir.exists():
        print(f"[ERROR] EasyOCR model directory not found!")
        print(f"[INFO] Please run EasyOCR once to download models first:")
        print(f"       python -c \"import easyocr; easyocr.Reader(['en'])\"")
        return False
    
    # Step 2: Find opt.txt with character list
    print(f"[INFO] Searching for opt.txt with character list...")
    opt_txt_path = find_opt_txt(model_dir)
    
    if not opt_txt_path:
        print(f"[ERROR] Could not find opt.txt file!")
        print(f"[INFO] The Tamil model may not be downloaded yet.")
        print(f"[INFO] Try running: python -c \"import easyocr; easyocr.Reader(['ta'])\"")
        print(f"[INFO] This will download the Tamil model, then run this script again.")
        return False
    
    print(f"[SUCCESS] Found opt.txt: {opt_txt_path}")
    
    # Step 3: Read the character list
    character_list = read_character_list(opt_txt_path)
    
    if not character_list:
        print(f"[ERROR] Could not extract character list from {opt_txt_path}")
        return False
    
    print(f"[SUCCESS] Extracted character list ({len(character_list)} characters)")
    
    # Step 4: Find or create ta.yaml
    yaml_path = find_tamil_yaml(model_dir)
    
    if yaml_path:
        print(f"[INFO] Found existing ta.yaml: {yaml_path}")
        success = update_tamil_yaml(yaml_path, character_list)
    else:
        # Create ta.yaml in user_network directory
        user_network = Path.home() / ".EasyOCR" / "user_network"
        yaml_path = user_network / "ta.yaml"
        print(f"[INFO] Creating new ta.yaml: {yaml_path}")
        success = create_tamil_yaml_from_scratch(yaml_path, character_list)
    
    # Step 5: Verify
    if success:
        print()
        print("=" * 70)
        print("[SUCCESS] Tamil language model fix applied!")
        print("=" * 70)
        print()
        print("You can now use EasyOCR with Tamil language:")
        print("    import easyocr")
        print("    reader = easyocr.Reader(['ta'])")
        print()
        return True
    else:
        print()
        print("[ERROR] Failed to apply the fix. See errors above.")
        return False


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
