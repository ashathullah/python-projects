import json
import os
import shutil
import re
from pathlib import Path

# Define base paths using absolute paths since the script is now outside assets
assets_dir = Path("assets")
base_dir = assets_dir / "organized_pdfs"

# Load the JSON data
json_path = assets_dir / "combined_data.json"
try:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"Error: JSON file not found at {json_path}")
    exit(1)
except json.JSONDecodeError:
    print(f"Error: Invalid JSON format in {json_path}")
    exit(1)

# Create the base directory if it doesn't exist
os.makedirs(base_dir, exist_ok=True)

# Track processed files to avoid duplicate copies
processed_files = set()
success_count = 0
error_count = 0
skipped_count = 0

def clean_filename(name, serial="unknown"):
    """Create a clean, valid filename from a candidate name and serial number"""
    if not name:
        return f"{serial}.pdf"
    
    # Clean the name: remove titles like திரு/திருமதி
    clean_name = name.replace("திரு ", "").replace("திருமதி ", "")
    
    # Create a filename with serial number and name
    filename = f"{serial}-{clean_name}"
    
    # Replace spaces with hyphens and remove invalid characters
    filename = filename.replace(" ", "-")
    filename = re.sub(r'[\\/*?:"<>|]', '', filename)
    
    return f"{filename}.pdf"

# Process each candidate entry
for entry in data:
    # Skip entries without proper data
    if not isinstance(entry, dict) or "district" not in entry or "pdf_file_path" not in entry or not entry["pdf_file_path"]:
        continue
    
    if "block_name" not in entry or "village_name" not in entry:
        continue
    
    # Skip entries that have a status value (not empty)
    if "status" in entry and entry["status"].strip():
        print(f"Skipping candidate {entry.get('name', 'Unknown')}: Status = {entry['status']}")
        skipped_count += 1
        continue
    
    # Create directory structure: district/block/village
    village_dir = base_dir / entry["district"] / entry["block_name"] / entry["village_name"]
    
    # Create directories (creates all parent directories as needed)
    os.makedirs(village_dir, exist_ok=True)
    
    # Source PDF path
    source_pdf_path = Path(entry["pdf_file_path"])
    absolute_source_path = Path().absolute() / source_pdf_path
    
    if not absolute_source_path.exists():
        print(f"Warning: Source PDF not found: {absolute_source_path}")
        error_count += 1
        continue
    
    # Generate a meaningful filename
    filename = clean_filename(entry.get("name"), entry.get("candidate_serial", "unknown"))
    
    # Destination path
    dest_pdf_path = village_dir / filename
    
    # Create a key to track processed files
    file_key = (str(source_pdf_path), str(dest_pdf_path))
    
    if file_key not in processed_files:
        try:
            # Copy the file
            shutil.copy2(absolute_source_path, dest_pdf_path)
            processed_files.add(file_key)
            success_count += 1
            
            # Update the path in the JSON data using relative paths from root
            entry["pdf_file_path"] = str(Path("assets/organized_pdfs") / entry["district"] / 
                                      entry["block_name"] / entry["village_name"] / filename)
            
            if success_count % 100 == 0:  # Log progress in batches
                print(f"Progress: {success_count} files processed successfully")
        except Exception as e:
            print(f"Error copying {source_pdf_path}: {e}")
            error_count += 1

# Save the updated JSON data
output_json_path = assets_dir / "combined_data_updated.json"
try:
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated JSON data saved to {output_json_path}")
except Exception as e:
    print(f"Error saving updated JSON: {e}")

print(f"File organization completed:")
print(f"- Successfully processed: {success_count} files")
print(f"- Files skipped (with status): {skipped_count} files")
print(f"- Errors encountered: {error_count} files")