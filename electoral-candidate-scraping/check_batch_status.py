import json
import os
import sys

# Constants
BATCH_INDEX_FILE = 'assets/batch_index.json'
BATCHES_FOLDER = 'assets/batches'

def load_batch_index():
    """Load the batch index file."""
    try:
        with open(BATCH_INDEX_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading batch index: {e}")
        return None

def load_batch(batch_filename):
    """Load a specific batch file."""
    try:
        batch_path = os.path.join(BATCHES_FOLDER, batch_filename)
        with open(batch_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading batch {batch_filename}: {e}")
        return None

def analyze_batch_entries(start_id=None, end_id=None):
    """
    Analyze entries in batches within the specified ID range.
    
    Args:
        start_id (int, optional): ID to start analysis from.
        end_id (int, optional): ID to end analysis at.
    """
    print(f"Analyzing entries in ID range: {start_id or 'Beginning'} to {end_id or 'End'}")
    
    # Load the batch index
    batch_index = load_batch_index()
    if not batch_index:
        print("No batch index found or error loading index. Exiting.")
        return
    
    print(f"Loaded batch index with {len(batch_index['batches'])} batches")
    
    # Convert start_id and end_id to integers
    start_id_int = int(start_id) if start_id is not None else None
    end_id_int = int(end_id) if end_id is not None else None
    
    # Find batches within range
    batches_to_analyze = []
    for batch_info in batch_index['batches']:
        batch_start = int(batch_info['start_id'])
        batch_end = int(batch_info['end_id'])
        
        # Check if batch overlaps with our range
        if (start_id_int is None or batch_end >= start_id_int) and \
           (end_id_int is None or batch_start <= end_id_int):
            batches_to_analyze.append(batch_info)
    
    print(f"Found {len(batches_to_analyze)} batches in range")
    
    # Collect statistics for entries in range
    total_entries = 0
    entries_by_status = {}
    entries_by_download_status = {}
    entries_in_range = []
    
    for batch_info in batches_to_analyze:
        batch_file = batch_info['filename']
        batch_data = load_batch(batch_file)
        
        if not batch_data:
            print(f"Error loading batch {batch_info['batch_id']}. Skipping.")
            continue
        
        for entry in batch_data:
            entry_id = int(entry.get('id', 0))
            
            # Check if the entry is in our range
            if (start_id_int is None or entry_id >= start_id_int) and \
               (end_id_int is None or entry_id <= end_id_int):
                # Count by status
                status = entry.get('status', 'unknown')
                entries_by_status[status] = entries_by_status.get(status, 0) + 1
                
                # Count by download_status
                download_status = entry.get('download_status', 'unknown')
                entries_by_download_status[download_status] = entries_by_download_status.get(download_status, 0) + 1
                
                total_entries += 1
                entries_in_range.append({
                    'id': entry_id,
                    'batch': batch_info['batch_id'],
                    'status': status,
                    'download_status': download_status
                })
    
    # Output statistics
    print(f"\nTotal entries in range {start_id_int}-{end_id_int}: {total_entries}")
    
    print("\nEntries by status:")
    for status, count in sorted(entries_by_status.items()):
        print(f"  {status}: {count} ({count/total_entries*100:.1f}%)")
    
    print("\nEntries by download_status:")
    for download_status, count in sorted(entries_by_download_status.items()):
        print(f"  {download_status}: {count} ({count/total_entries*100:.1f}%)")
    
    # Print a sample of entries in range
    if entries_in_range:
        print("\nSample of entries in range:")
        for i, entry in enumerate(entries_in_range[:10]):  # Show up to 10 entries
            print(f"  ID: {entry['id']}, Batch: {entry['batch']}, Status: {entry['status']}, Download Status: {entry['download_status']}")
        
        if len(entries_in_range) > 10:
            print(f"  ... and {len(entries_in_range) - 10} more")
    else:
        print("\nNo entries found in the specified range.")

def reset_entry_statuses(start_id=None, end_id=None, dry_run=True):
    """
    Reset the status of entries within the specified ID range to 'not_processed'.
    
    Args:
        start_id (int, optional): ID to start from.
        end_id (int, optional): ID to end at.
        dry_run (bool): If True, only show what would be changed without making changes.
    """
    print(f"{'[DRY RUN] ' if dry_run else ''}Resetting entry statuses in ID range: {start_id or 'Beginning'} to {end_id or 'End'}")
    
    # Load the batch index
    batch_index = load_batch_index()
    if not batch_index:
        print("No batch index found or error loading index. Exiting.")
        return
    
    # Convert start_id and end_id to integers
    start_id_int = int(start_id) if start_id is not None else None
    end_id_int = int(end_id) if end_id is not None else None
    
    # Find batches within range
    batches_to_update = []
    for batch_info in batch_index['batches']:
        batch_start = int(batch_info['start_id'])
        batch_end = int(batch_info['end_id'])
        
        # Check if batch overlaps with our range
        if (start_id_int is None or batch_end >= start_id_int) and \
           (end_id_int is None or batch_start <= end_id_int):
            batches_to_update.append(batch_info)
    
    print(f"Found {len(batches_to_update)} batches in range")
    
    # Process each batch
    entries_reset = 0
    
    for batch_info in batches_to_update:
        batch_id = batch_info['batch_id']
        batch_file = batch_info['filename']
        
        # Load the batch data
        batch_path = os.path.join(BATCHES_FOLDER, batch_file)
        try:
            with open(batch_path, 'r', encoding='utf-8') as file:
                batch_data = json.load(file)
        except Exception as e:
            print(f"Error loading batch {batch_id}: {e}")
            continue
        
        # Track if this batch was modified
        batch_modified = False
        
        # Process each entry in the batch
        for entry in batch_data:
            entry_id = int(entry.get('id', 0))
            
            # Check if the entry is in our range
            if (start_id_int is None or entry_id >= start_id_int) and \
               (end_id_int is None or entry_id <= end_id_int):
                
                # Check if the entry needs resetting
                old_status = entry.get('status', 'unknown')
                if old_status != 'not_processed':
                    if not dry_run:
                        entry['status'] = 'not_processed'
                        if 'download_status' in entry:
                            del entry['download_status']
                    entries_reset += 1
                    batch_modified = True
                    print(f"  Reset entry {entry_id} in batch {batch_id} from '{old_status}' to 'not_processed'")
        
        # Save the batch if modified and not in dry run mode
        if batch_modified and not dry_run:
            try:
                with open(batch_path, 'w', encoding='utf-8') as file:
                    json.dump(batch_data, file, indent=2, ensure_ascii=False)
                print(f"Saved changes to batch {batch_id}")
                
                # Also update the batch status in the index
                batch_info['download_status'] = 'not_started'
            except Exception as e:
                print(f"Error saving batch {batch_id}: {e}")
    
    # Save the batch index if not in dry run mode and if any batch was modified
    if not dry_run and any(batch['download_status'] == 'not_started' for batch in batches_to_update):
        try:
            with open(BATCH_INDEX_FILE, 'w', encoding='utf-8') as file:
                json.dump(batch_index, file, indent=2, ensure_ascii=False)
            print("Updated batch index file")
        except Exception as e:
            print(f"Error saving batch index: {e}")
    
    print(f"\n{entries_reset} entries {'would be' if dry_run else 'were'} reset")

if __name__ == "__main__":
    # Basic command line argument parsing
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python check_batch_status.py analyze [start_id] [end_id]")
        print("  python check_batch_status.py reset [start_id] [end_id] [--apply]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "analyze":
        start_id = sys.argv[2] if len(sys.argv) > 2 else None
        end_id = sys.argv[3] if len(sys.argv) > 3 else None
        analyze_batch_entries(start_id, end_id)
    
    elif command == "reset":
        start_id = sys.argv[2] if len(sys.argv) > 2 else None
        end_id = sys.argv[3] if len(sys.argv) > 3 else None
        dry_run = "--apply" not in sys.argv
        reset_entry_statuses(start_id, end_id, dry_run)
    
    else:
        print(f"Unknown command: {command}")
        print("Available commands: analyze, reset")
        sys.exit(1)
