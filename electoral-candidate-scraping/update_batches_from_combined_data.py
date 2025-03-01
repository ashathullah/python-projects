import json
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("batch_update.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File paths
COMBINED_DATA_PATH = "assets/combined_data_updated.json"
BATCH_INDEX_PATH = "assets/batch_index.json"
BATCH_DIR = "assets/batches"

def load_json(file_path):
    """Load JSON data from file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None

def save_json(data, file_path):
    """Save JSON data to file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving {file_path}: {e}")
        return False

def main():
    # Load the combined data
    logger.info(f"Loading combined data from {COMBINED_DATA_PATH}")
    combined_data = load_json(COMBINED_DATA_PATH)
    if not combined_data:
        logger.error("Failed to load combined data")
        return
    
    # Create a dictionary for quick lookup of entries by ID
    combined_data_dict = {entry.get('id'): entry for entry in combined_data if entry.get('id')}
    logger.info(f"Loaded {len(combined_data_dict)} entries from combined data")
    
    # Load the batch index
    logger.info(f"Loading batch index from {BATCH_INDEX_PATH}")
    batch_index = load_json(BATCH_INDEX_PATH)
    if not batch_index:
        logger.error("Failed to load batch index")
        return
    
    # Process each batch
    processed_batches = 0
    total_entries_updated = 0
    batch_status_updates = {}
    
    for batch in batch_index.get('batches', []):
        batch_id = batch.get('batch_id')
        batch_file = batch.get('filepath')
        
        # Skip if filepath is not available
        if not batch_file:
            logger.warning(f"Batch {batch_id} has no filepath")
            continue
        
        # Check if batch file exists
        if not os.path.exists(batch_file):
            logger.warning(f"Batch file {batch_file} does not exist")
            continue
        
        # Load the batch data
        batch_data = load_json(batch_file)
        if not batch_data:
            logger.error(f"Failed to load batch {batch_id} from {batch_file}")
            continue
        
        # Track if this batch was updated
        batch_updated = False
        entries_updated = 0
        
        # Update entries with matching IDs
        for entry in batch_data:
            entry_id = entry.get('id')
            if entry_id and entry_id in combined_data_dict:
                combined_entry = combined_data_dict[entry_id]
                
                # Update the download_status field
                if 'download_status' in combined_entry:
                    entry['download_status'] = combined_entry['download_status']
                    batch_updated = True
                    entries_updated += 1
                
                # Update the pdf_file_path field
                if 'pdf_file_path' in combined_entry:
                    entry['pdf_file_path'] = combined_entry['pdf_file_path']
                    batch_updated = True
        
        # Save the updated batch if changes were made
        if batch_updated:
            logger.info(f"Updating batch {batch_id} with {entries_updated} modified entries")
            if save_json(batch_data, batch_file):
                processed_batches += 1
                total_entries_updated += entries_updated
                
                # Mark batch as processed in batch_index if all entries are processed
                all_processed = all(entry.get('download_status') == 'completed' for entry in batch_data)
                batch_status_updates[batch_id] = "completed" if all_processed else "in_progress"
            else:
                logger.error(f"Failed to save updated batch {batch_id}")
    
    # Update batch index with processed status
    if batch_status_updates:
        for batch in batch_index.get('batches', []):
            batch_id = batch.get('batch_id')
            if batch_id in batch_status_updates:
                batch['status'] = batch_status_updates[batch_id]
        
        # Save the updated batch index
        logger.info(f"Updating batch index with {len(batch_status_updates)} status updates")
        if save_json(batch_index, BATCH_INDEX_PATH):
            logger.info(f"Batch index successfully updated")
        else:
            logger.error(f"Failed to update batch index")
    
    logger.info(f"Update completed: {processed_batches} batches processed, {total_entries_updated} entries updated")

if __name__ == "__main__":
    main()
