import pandas as pd
import json
import os
from pathlib import Path
import math

def excel_to_json(limit=None, batch_size=500):
    """
    Convert Excel data to JSON batch files and create an index file.
    
    Args:
        limit (int, optional): Limit the number of rows to process. None means process all.
        batch_size (int): Number of entries per batch file.
    """
    # Define file paths
    script_dir = Path(__file__).parent
    excel_file = script_dir / "assets" / "combined_data.xlsx"
    output_dir = script_dir / "assets" / "batches"
    index_file = script_dir / "assets" / "batch_index.json"
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if Excel file exists
    if not excel_file.exists():
        print(f"Error: Excel file not found at {excel_file}")
        return False
    
    try:
        # Read Excel file
        print(f"Reading Excel file from {excel_file}...")
        df = pd.read_excel(excel_file)
        
        # Apply limit if specified
        if limit and limit > 0:
            df = df.head(limit)
            print(f"Limiting data to {limit} entries")
        else:
            print(f"Processing all {len(df)} entries")
        
        # Convert DataFrame to list of dictionaries
        data_list = df.to_dict(orient='records')
        
        # Add status field and additional fields to each entry
        count = 1
        for entry in data_list:
            entry['id'] = count
            entry['status'] = 'not_processed'
            entry['pdf_file_path'] = ''
            entry['image_file_path'] = ''
            entry['extracted_data'] = {}
            count += 1
        
        # Calculate number of batches
        total_entries = len(data_list)
        num_batches = math.ceil(total_entries / batch_size)
        print(f"Creating {num_batches} batch files with {batch_size} entries per batch")
        
        # Create batch index to track progress
        batch_index = {
            "total_entries": total_entries,
            "batch_size": batch_size,
            "num_batches": num_batches,
            "batches": []
        }
        
        # Create batch files
        for i in range(num_batches):
            start_idx = i * batch_size
            end_idx = min((i + 1) * batch_size, total_entries)
            batch_data = data_list[start_idx:end_idx]
            
            batch_filename = f"batch_{i+1}.json"
            batch_filepath = output_dir / batch_filename
            
            # Save batch to JSON file
            with open(batch_filepath, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=4, ensure_ascii=False)
            
            # Add batch info to index
            batch_info = {
                "batch_id": i + 1,
                "filename": batch_filename,
                "filepath": str(batch_filepath.relative_to(script_dir)),
                "entries": len(batch_data),
                "start_id": batch_data[0]['id'],
                "end_id": batch_data[-1]['id'],
                "status": "not_started"  # Options: not_started, in_progress, completed
            }
            batch_index["batches"].append(batch_info)
            
            print(f"Created batch {i+1}/{num_batches}: {batch_filepath}")
        
        # Save the batch index
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(batch_index, f, indent=4, ensure_ascii=False)
        
        print(f"Batch index created at {index_file}")
        print(f"Total entries processed: {total_entries}")
        return True
    
    except Exception as e:
        print(f"Error converting Excel to JSON: {e}")
        return False

if __name__ == "__main__":
    # Create assets directory if it doesn't exist
    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    # Execute the conversion with optional limit and configurable batch size
    # Set limit=None to process all entries
    excel_to_json(limit=None, batch_size=500)
