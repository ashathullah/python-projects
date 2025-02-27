import pandas as pd
import json
import os
from pathlib import Path

def excel_to_json(limit=2000):
    # Define file paths
    script_dir = Path(__file__).parent
    excel_file = script_dir / "assets" / "combined_data.xlsx"
    output_file = script_dir / "assets" / "combined_data.json"
    
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
        
        # Convert DataFrame to list of dictionaries
        data_list = df.to_dict(orient='records')
        
        # Add status field and additional fields to each entry
        count = 1
        for entry in data_list:
            entry['id'] = count
            entry['status'] = 'not_processed'
            entry['pdf_file_path'] = ''  # Store the location of the PDF file
            entry['image_file_path'] = ''  # Store the location of the image file
            entry['extracted_data'] = {}  # Store the extracted data from the image
            count += 1
        
        # Save as JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4, ensure_ascii=False)
        
        print(f"Successfully converted Excel data to JSON and saved at {output_file}")
        print(f"Total entries: {len(data_list)}")
        return True
    
    except Exception as e:
        print(f"Error converting Excel to JSON: {e}")
        return False

if __name__ == "__main__":
    # Create assets directory if it doesn't exist
    Path("assets").mkdir(exist_ok=True)
    
    # Execute the conversion with default limit
    excel_to_json()
