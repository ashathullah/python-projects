import json
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("status_update.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File paths
COMBINED_DATA_PATH = "assets/combined_data.json"
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
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {file_path}: {e}")
        return False

def get_batch_files():
    """Get all batch JSON files from the batch directory."""
    batch_files = []
    
    # Try to load batch index file to get the list of batch files
    batch_index = load_json(BATCH_INDEX_PATH)
    if batch_index and "batches" in batch_index:
        for batch in batch_index["batches"]:
            if "filepath" in batch:
                batch_files.append(batch["filepath"])
    else:
        # Fallback to scanning the directory if batch index is not available
        logger.warning("Batch index file not found or invalid. Scanning batch directory.")
        batch_files = [os.path.join(BATCH_DIR, f) for f in os.listdir(BATCH_DIR) 
                      if f.endswith('.json') and os.path.isfile(os.path.join(BATCH_DIR, f))]
    
    return batch_files

def update_combined_data_status():
    """Update the status field in combined_data.json with values from batch files."""
    # Load the combined data
    logger.info(f"Loading combined data from {COMBINED_DATA_PATH}")
    combined_data = load_json(COMBINED_DATA_PATH)
    if not combined_data:
        logger.error("Failed to load combined data")
        return False
    
    # Create a dictionary for quick lookup of combined data entries by ID
    combined_data_dict = {entry.get('id'): entry for entry in combined_data if entry.get('id')}
    logger.info(f"Loaded {len(combined_data_dict)} entries from combined data")
    
    # Get all batch files
    batch_files = get_batch_files()
    logger.info(f"Found {len(batch_files)} batch files to process")
    
    # Track the number of updates
    status_updates = 0
    pdf_path_updates = 0
    download_status_updates = 0
    
    # Process each batch file
    for batch_file in batch_files:
        if not os.path.exists(batch_file):
            logger.warning(f"Batch file {batch_file} does not exist")
            continue
            
        logger.info(f"Processing batch file: {batch_file}")
        batch_data = load_json(batch_file)
        
        if not batch_data:
            logger.error(f"Failed to load batch file: {batch_file}")
            continue
        
        # Update the status field in combined_data
        for entry in batch_data:
            entry_id = entry.get('id')
            if entry_id and entry_id in combined_data_dict:
                # Copy the status from batch file to combined data if it exists
                if 'status' in entry:
                    # Check if status exists in batch entry (even if empty)
                    combined_data_dict[entry_id]['status'] = entry['status']
                    status_updates += 1
                    logger.debug(f"Updated status for ID {entry_id}: {entry['status']}")
                
                # # Copy the download_status if it exists
                # if 'download_status' in entry:
                #     combined_data_dict[entry_id]['download_status'] = entry['download_status']
                #     download_status_updates += 1
                
                # # Copy the pdf_file_path if it exists
                # if 'pdf_file_path' in entry:
                #     combined_data_dict[entry_id]['pdf_file_path'] = entry['pdf_file_path']
                #     pdf_path_updates += 1
    
    logger.info(f"Updated {status_updates} status fields")
    
    # Save the updated combined data
    logger.info(f"Saving updated combined data to {COMBINED_DATA_PATH}")
    # Convert the dictionary back to a list before saving
    updated_combined_data = list(combined_data_dict.values())
    if save_json(updated_combined_data, COMBINED_DATA_PATH):
        logger.info(f"Successfully saved updated combined data with {len(updated_combined_data)} entries")
        return True
    else:
        logger.error("Failed to save updated combined data")
        return False

def main():
    """Main function."""
    logger.info("Starting update of combined data status")
    if update_combined_data_status():
        logger.info("Successfully updated combined data status")
    else:
        logger.error("Failed to update combined data status")

if __name__ == "__main__":
    main()
