import json
import os
from pathlib import Path

# Constants
BATCH_INDEX_FILE = 'assets/batch_index.json'
BATCHES_FOLDER = 'assets/batches'

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

def filter_entries_by_status(entries):
    """Filter out entries with non-empty status values."""
    return [entry for entry in entries if not entry.get('status')]

def reorder_ids(entries):
    """Reorder IDs sequentially starting from 1."""
    for i, entry in enumerate(entries, 1):
        entry['id'] = i
    return entries

def process_batch_file(batch_file):
    """Process a single batch file."""
    file_path = os.path.join(BATCHES_FOLDER, batch_file)
    data = load_json_file(file_path)
    if data is None:
        return False, 0
    
    # Record original count for reporting
    original_count = len(data)
    
    # Filter out entries with non-empty status
    filtered_data = filter_entries_by_status(data)
    filtered_count = len(filtered_data)
    
    # Reorder IDs if any entries were removed
    if filtered_count < original_count:
        filtered_data = reorder_ids(filtered_data)
    
    # Save the updated data back to the file
    success = save_json_file(filtered_data, file_path)
    return success, (original_count, filtered_count)

def update_batch_index(batch_index, batch_counts):
    """Update the batch index with new entry counts and ID ranges."""
    current_id = 1
    
    for i, batch in enumerate(batch_index['batches']):
        batch_file = batch['filename']
        if batch_file in batch_counts:
            # Update entry count
            batch['entries'] = batch_counts[batch_file][1]
            
            # Update ID range
            batch['start_id'] = current_id
            batch['end_id'] = current_id + batch['entries'] - 1
            current_id += batch['entries']
    
    # Update total entries
    batch_index['total_entries'] = sum(counts[1] for counts in batch_counts.values())
    
    return batch_index

def main():
    """Main function to filter entries and update the batch index."""
    # Load the batch index
    batch_index = load_json_file(BATCH_INDEX_FILE)
    if not batch_index:
        print("Failed to load the batch index file.")
        return
    
    print(f"Processing {len(batch_index['batches'])} batch files...")
    
    # Process each batch file
    successful_batches = 0
    removed_counts = 0
    batch_counts = {}
    
    for batch in batch_index['batches']:
        batch_file = batch['filename']
        print(f"Processing {batch_file}...")
        
        success, (original_count, filtered_count) = process_batch_file(batch_file)
        batch_counts[batch_file] = (original_count, filtered_count)
        
        if success:
            successful_batches += 1
            removed_entries = original_count - filtered_count
            removed_counts += removed_entries
            print(f"  Removed {removed_entries} entries with non-empty status")
        else:
            print(f"Failed to process {batch_file}")
    
    print(f"\nSuccessfully processed {successful_batches} out of {len(batch_index['batches'])} batch files.")
    print(f"Total entries removed: {removed_counts}")
    
    # Update the batch index with new entry counts and ID ranges
    updated_batch_index = update_batch_index(batch_index, batch_counts)
    
    # Save the updated batch index
    if save_json_file(updated_batch_index, BATCH_INDEX_FILE):
        print(f"Successfully updated the batch index file.")
        print(f"New total entry count: {updated_batch_index['total_entries']}")
    else:
        print(f"Failed to update the batch index file.")

if __name__ == "__main__":
    # Ensure the batches folder exists
    if not os.path.exists(BATCHES_FOLDER):
        print(f"Error: Batches folder {BATCHES_FOLDER} not found.")
    else:
        main()
