import json
import os
import math
import glob
from pathlib import Path

# Constants
BATCH_INDEX_FILE = 'assets/batch_index.json'
BATCHES_FOLDER = 'assets/batches'
ENTRIES_PER_BATCH = 500  # Fixed number of entries per batch

def load_json_file(file_path):
    """Load JSON data from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading JSON file {file_path}: {e}")
        return None

def save_json_file(data, file_path):
    """Save JSON data to a file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving JSON file {file_path}: {e}")
        return False

def cleanup_unused_batch_files(used_filenames):
    """Delete batch files that are not in the used_filenames list."""
    batch_pattern = os.path.join(BATCHES_FOLDER, "batch_*.json")
    all_batch_files = [os.path.basename(f) for f in glob.glob(batch_pattern)]
    
    files_to_remove = [f for f in all_batch_files if f not in used_filenames]
    
    if not files_to_remove:
        print("No unused batch files to remove.")
        return
    
    removed_count = 0
    for filename in files_to_remove:
        file_path = os.path.join(BATCHES_FOLDER, filename)
        try:
            os.remove(file_path)
            removed_count += 1
            print(f"Removed unused batch file: {filename}")
        except Exception as e:
            print(f"Failed to remove {filename}: {e}")
    
    print(f"Removed {removed_count} unused batch files.")

def filter_and_rebalance():
    """
    Filter out entries with non-empty status values and rebalance the remaining entries
    into batches of 500 each.
    """
    # Load batch index
    batch_index = load_json_file(BATCH_INDEX_FILE)
    if not batch_index:
        print("Failed to load the batch index file.")
        return False
    
    print(f"Loading data from {len(batch_index['batches'])} batch files...")
    
    # Collect all entries from all batch files
    all_entries = []
    for batch in batch_index['batches']:
        batch_file = batch['filename']
        batch_path = os.path.join(BATCHES_FOLDER, batch_file)
        
        batch_data = load_json_file(batch_path)
        if batch_data:
            all_entries.extend(batch_data)
            print(f"Loaded {len(batch_data)} entries from {batch_file}")
        else:
            print(f"Failed to load {batch_file}")
    
    original_total = len(all_entries)
    print(f"Original total entries: {original_total}")
    
    # 1. FILTER STEP: Filter out entries with non-empty status
    filtered_entries = [entry for entry in all_entries if not entry.get('status')]
    filtered_total = len(filtered_entries)
    removed_count = original_total - filtered_total
    
    print(f"Removed {removed_count} entries with non-empty status values")
    print(f"Remaining entries: {filtered_total}")
    
    # 2. REBALANCE STEP: Sort and reindex the entries
    filtered_entries.sort(key=lambda x: x.get('id', 0))
    
    # Reorder IDs sequentially
    for i, entry in enumerate(filtered_entries, 1):
        entry['id'] = i
    
    print(f"Reindexed {filtered_total} entries with sequential IDs")
    
    # 3. REDISTRIBUTE STEP: Calculate new batch distribution
    num_batches = math.ceil(filtered_total / ENTRIES_PER_BATCH)
    print(f"Redistributing entries into {num_batches} batches with {ENTRIES_PER_BATCH} entries per batch...")
    
    # Create new batch index
    new_batch_index = {
        "total_entries": filtered_total,
        "batch_size": ENTRIES_PER_BATCH,
        "num_batches": num_batches,
        "batches": []
    }
    
    # Keep track of batch filenames that are used in the new index
    used_filenames = []
    
    # 4. SAVE STEP: Create and save new batch files
    for i in range(num_batches):
        start_idx = i * ENTRIES_PER_BATCH
        end_idx = min((i + 1) * ENTRIES_PER_BATCH, filtered_total)
        batch_data = filtered_entries[start_idx:end_idx]
        
        batch_filename = f"batch_{i+1}.json"
        used_filenames.append(batch_filename)
        batch_filepath = os.path.join(BATCHES_FOLDER, batch_filename)
        
        # Save the batch file
        if save_json_file(batch_data, batch_filepath):
            print(f"Saved batch {i+1}/{num_batches} with {len(batch_data)} entries")
        else:
            print(f"Failed to save batch {i+1}")
            return False
        
        # Determine download status for this batch
        batch_status = "not_started"
        completed_entries = sum(1 for entry in batch_data if entry.get('download_status') == 'completed')
        total_entries_in_batch = len(batch_data)
        
        if completed_entries == total_entries_in_batch:
            batch_status = "completed"
        elif completed_entries > 0:
            batch_status = "in_progress"
        
        # Add batch info to index
        batch_info = {
            "batch_id": i + 1,
            "filename": batch_filename,
            "filepath": os.path.join("assets", "batches", batch_filename).replace("\\", "/"),
            "entries": len(batch_data),
            "start_id": batch_data[0]['id'],
            "end_id": batch_data[-1]['id'],
            "download_status": batch_status
        }
        
        new_batch_index["batches"].append(batch_info)
    
    # 5. UPDATE INDEX STEP: Save the updated batch index
    if save_json_file(new_batch_index, BATCH_INDEX_FILE):
        print(f"Successfully updated batch index")
        
        # 6. CLEANUP STEP: Remove unused batch files
        cleanup_unused_batch_files(used_filenames)
        
        return True
    else:
        print(f"Failed to update batch index")
        return False

def main():
    """Main function to run both filtering and rebalancing in one go."""
    print("Starting combined filtering and rebalancing process")
    print("---------------------------------------------------")
    print("Step 1: Filter out entries with non-empty status")
    print("Step 2: Rebalance remaining entries into 500-entry batches")
    print("Step 3: Update batch index and clean up unused files")
    print("---------------------------------------------------")
    
    # Ensure the batches folder exists
    os.makedirs(BATCHES_FOLDER, exist_ok=True)
    
    # Run the combined process
    success = filter_and_rebalance()
    
    if success:
        print("\n===================================================")
        print("✅ Filtering and rebalancing completed successfully!")
        print(f"   All batches now contain {ENTRIES_PER_BATCH} entries (except possibly the last one)")
        print("   All entries with non-empty status values have been removed")
        print("===================================================")
    else:
        print("\n===================================================")
        print("❌ Filtering and rebalancing process failed!")
        print("===================================================")

if __name__ == "__main__":
    main()
