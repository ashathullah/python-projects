import json
import os
import time
import random
import requests
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from google.genai import types
from google import genai
from pathlib import Path
import re
import unicodedata

# Constants
BATCH_INDEX_FILE = 'assets/batch_index.json'
BATCHES_FOLDER = 'assets/batches'
IMAGES_FOLDER = 'assets/images'
PDFS_FOLDER = 'assets/pdfs'
MIN_DELAY = 1  # Minimum delay between requests (seconds)
MAX_DELAY = 2  # Maximum delay between requests (seconds)

# Configuration variables
# Set start_id to None to process all entries, or set a specific ID to skip entries before that ID
START_ID = 10569  # Example: 2001 would skip the first 2000 entries
# Set end_id to None to process all entries after start_id, or set a specific ID to stop processing after that ID
END_ID = 12818  # Example: 3000 would process entries from start_id up to 3000
# Size of each batch (default is 500)
BATCH_SIZE = 500

# Ensure directories exist
Path(IMAGES_FOLDER).mkdir(parents=True, exist_ok=True)
Path(PDFS_FOLDER).mkdir(parents=True, exist_ok=True)

# Get absolute path for PDF downloads
ABSOLUTE_PDFS_FOLDER = os.path.abspath(PDFS_FOLDER)

def sanitize_filename(name):
    """Convert spaces to hyphens, remove special characters, and handle Tamil text in filename."""
    # Replace spaces with hyphens
    name = re.sub(r'\s+', '-', name)
    # Remove special characters, allowing Tamil characters
    name = re.sub(r'[^\w\-\u0B80-\u0BFF]', '', name)
    # Ensure filename is not too long
    return name[:100]

def solve_captcha(image_path):
    """Use Gemini to solve the captcha."""
    try:
        # Initialize the Gemini client
        client = genai.Client(api_key="AIzaSyDjT8cgnSOgoK5CdQ1G171H8SqJ7CKn6X8")
        
        # Define the messages for the chat
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=["This is a CAPTCHA image. Please tell me only the characters or numbers shown in this image. Return only the exact CAPTCHA text, nothing else.",
                          types.Part.from_bytes(data=image_data, mime_type="image/png")]
            )
        
        # Extract the content of the response
        captcha_text = response.text
        print(f"{response}")
        # Clean up the response to get just the CAPTCHA text
        captcha_text = captcha_text.strip()
        
        # Remove common text patterns in AI responses
        prefixes = ["The CAPTCHA text is ", "CAPTCHA text: ", "The text in the CAPTCHA is ", "The CAPTCHA reads "]
        for prefix in prefixes:
            if captcha_text.startswith(prefix):
                captcha_text = captcha_text[len(prefix):]
        
        # Remove quotes if present
        captcha_text = captcha_text.strip('"\'')
        
        return captcha_text
    except Exception as e:
        print(f"Error solving CAPTCHA: {e}")
        return None

def load_batch_index():
    """Load the batch index file."""
    try:
        with open(BATCH_INDEX_FILE, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading batch index: {e}")
        return None

def save_batch_index(batch_index):
    """Save the batch index file."""
    try:
        with open(BATCH_INDEX_FILE, 'w', encoding='utf-8') as file:
            json.dump(batch_index, file, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving batch index: {e}")
        return False

def load_batch(batch_filename):
    """Load a specific batch file."""
    try:
        batch_path = os.path.join(BATCHES_FOLDER, batch_filename)
        with open(batch_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading batch {batch_filename}: {e}")
        return None

def save_batch(batch_data, batch_filename):
    """Save data back to the batch file."""
    try:
        batch_path = os.path.join(BATCHES_FOLDER, batch_filename)
        with open(batch_path, 'w', encoding='utf-8') as file:
            json.dump(batch_data, file, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving batch {batch_filename}: {e}")
        return False

def process_entry(entry, driver):
    """Process a single entry: fetch captcha, solve it, and download PDF."""
    entry_id = entry.get('id', 'unknown')
    url = entry.get('download_url')
    start_time = time.time()
    captcha_images = []  # Track all created captcha images for later cleanup
    
    if not url:
        print(f"Entry {entry_id}: No download URL found")
        entry['download_status'] = 'error_no_url'
        return False, 0

    try:
        print(f"Processing entry {entry_id}: Navigating to {url}")
        print(f"Start time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        driver.get(url)
        
        # Variables for CAPTCHA retry logic
        captcha_solved = False
        captcha_attempts = 0
        max_captcha_attempts = 5  # Initial attempt + 4 retries

        # CAPTCHA solving loop
        while not captcha_solved and captcha_attempts < max_captcha_attempts:
            captcha_attempts += 1
            print(f"Entry {entry_id}: CAPTCHA attempt {captcha_attempts}/{max_captcha_attempts}")

            # Wait for page to load and get the captcha image
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "capt"))
                )
                captcha_img = driver.find_element(By.ID, "capt")

                # Save the captcha image with attempt number
                img_path = f"{IMAGES_FOLDER}/{entry_id}_attempt{captcha_attempts}.png"
                captcha_img.screenshot(img_path)
                captcha_images.append(img_path)  # Add to list of images for cleanup
                print(f"Entry {entry_id}: Saved captcha image to {img_path}")

                # Get the initial file count in downloads folder
                initial_files = set(os.listdir(ABSOLUTE_PDFS_FOLDER))

                # Solve the captcha
                captcha_solution = solve_captcha(img_path)
                if not captcha_solution:
                    print(f"Entry {entry_id}: Failed to solve captcha on attempt {captcha_attempts}")
                    if captcha_attempts < max_captcha_attempts:
                        # Click the reload button to get a new CAPTCHA
                        try:
                            reload_button = driver.find_element(By.CLASS_NAME, "crossRotate")
                            reload_button.click()
                            print(f"Entry {entry_id}: Clicked reload button for new CAPTCHA")
                            time.sleep(2)  # Wait for new CAPTCHA to load
                            continue
                        except Exception as e:
                            print(f"Entry {entry_id}: Failed to find or click reload button: {e}")
                            entry['download_status'] = 'error_captcha_reload_failed'
                            cleanup_captcha_images(captcha_images)
                            return False, time.time() - start_time
                    else:
                        entry['download_status'] = 'error_captcha_unsolved'
                        cleanup_captcha_images(captcha_images)
                        return False, time.time() - start_time

                print(f"Entry {entry_id}: Solved captcha - '{captcha_solution}'")

                # Fill in the captcha solution
                captcha_input = driver.find_element(By.ID, "t1")
                captcha_input.clear()
                captcha_input.send_keys(captcha_solution)

                # Click the submit button
                submit_button = driver.find_element(By.ID, "show_corp")
                submit_button.click()

                # Wait for the PDF download to start
                time.sleep(3)  # Simple wait for the download to initialize

                # Check if there's an error message (incorrect CAPTCHA)
                try:
                    error_elements = driver.find_elements(By.XPATH, "//div[contains(text(), 'Invalid') or contains(text(), 'Error')]") 
                    if error_elements:
                        print(f"Entry {entry_id}: Invalid CAPTCHA or other error on attempt {captcha_attempts}")
                        if captcha_attempts < max_captcha_attempts:
                            # Click the reload button to get a new CAPTCHA
                            try:
                                reload_button = driver.find_element(By.CLASS_NAME, "crossRotate")
                                reload_button.click()
                                print(f"Entry {entry_id}: Clicked reload button for new CAPTCHA after error")
                                time.sleep(2)  # Wait for new CAPTCHA to load
                                continue
                            except Exception as e:
                                print(f"Entry {entry_id}: Failed to find or click reload button after error: {e}")
                                entry['download_status'] = 'error_captcha_reload_failed'
                                cleanup_captcha_images(captcha_images)
                                return False, time.time() - start_time
                        else:
                            entry['download_status'] = 'error_invalid_captcha'
                            cleanup_captcha_images(captcha_images)
                            return False, time.time() - start_time
                except:
                    pass  # No error found, continue

                # Wait for download to complete and find the downloaded file
                max_wait = 30  # Maximum seconds to wait for download
                waited = 0
                downloaded_file = None

                while waited < max_wait:
                    # Get current files in download directory
                    current_files = set(os.listdir(ABSOLUTE_PDFS_FOLDER))
                    # Find new files
                    new_files = current_files - initial_files
                    # Filter for PDF files
                    new_pdf_files = [f for f in new_files if f.endswith('.pdf')]

                    if new_pdf_files:
                        downloaded_file = new_pdf_files[0]  # Get the first new PDF file
                        print(f"Entry {entry_id}: Found downloaded PDF: {downloaded_file}")
                        captcha_solved = True
                        break

                    time.sleep(1)
                    waited += 1

                if not downloaded_file:
                    if captcha_attempts < max_captcha_attempts:
                        print(f"Entry {entry_id}: No PDF downloaded, trying again with new CAPTCHA")
                        try:
                            reload_button = driver.find_element(By.CLASS_NAME, "crossRotate")
                            reload_button.click()
                            print(f"Entry {entry_id}: Clicked reload button for new CAPTCHA after no download")
                            time.sleep(2)  # Wait for new CAPTCHA to load
                            continue
                        except Exception as e:
                            print(f"Entry {entry_id}: Failed to find or click reload button after no download: {e}")
                            entry['download_status'] = 'error_captcha_reload_failed'
                            cleanup_captcha_images(captcha_images)
                            return False, time.time() - start_time
                    else:
                        print(f"Entry {entry_id}: No PDF downloaded after all attempts")
                        entry['download_status'] = 'error_no_download'
                        cleanup_captcha_images(captcha_images)
                        return False, time.time() - start_time

                # Create directory structure based on district, block, and village
                district = sanitize_filename(entry.get('district', ''))
                block = sanitize_filename(entry.get('block_name', ''))
                village = sanitize_filename(entry.get('village_name', ''))

                # Create target directory
                target_dir = os.path.join(PDFS_FOLDER, district, block, village)
                os.makedirs(target_dir, exist_ok=True)

                # Create filename based on person's name with entry ID as prefix
                person_name = sanitize_filename(entry.get('name', f"person_{entry_id}"))
                target_filename = f"{entry_id}-{person_name}.pdf"
                target_path = os.path.join(target_dir, target_filename)

                # Move the downloaded file to the target location
                source_path = os.path.join(ABSOLUTE_PDFS_FOLDER, downloaded_file)

                try:
                    # Use os.replace to avoid cross-device issues
                    os.replace(source_path, target_path)
                    print(f"Entry {entry_id}: Moved file to {target_path}")
                except Exception as e:
                    # If replace fails, try copy and delete
                    import shutil
                    shutil.copy2(source_path, target_path)
                    os.remove(source_path)
                    print(f"Entry {entry_id}: Copied file to {target_path}")

                # Store the file path in the entry
                entry['pdf_file_path'] = os.path.relpath(target_path, start=os.path.dirname(PDFS_FOLDER))
                entry['download_status'] = 'completed'

                elapsed_time = time.time() - start_time
                print(f"Entry {entry_id}: Processed successfully in {elapsed_time:.2f} seconds")
                print(f"End time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Cleanup CAPTCHA images
                cleanup_captcha_images(captcha_images)
                return True, elapsed_time

            except (TimeoutException, NoSuchElementException) as e:
                print(f"Entry {entry_id}: Element not found on attempt {captcha_attempts} - {e}")
                if captcha_attempts < max_captcha_attempts:
                    # Try reloading the page
                    driver.refresh()
                    print(f"Entry {entry_id}: Reloaded page for attempt {captcha_attempts+1}")
                    time.sleep(3)
                    continue
                else:
                    entry['download_status'] = 'error_element_not_found'
                    # Cleanup CAPTCHA images
                    cleanup_captcha_images(captcha_images)
                    return False, time.time() - start_time

    except Exception as e:
        print(f"Entry {entry_id}: Processing error - {e}")
        entry['download_status'] = f'error_processing'
        # Cleanup CAPTCHA images
        cleanup_captcha_images(captcha_images)
        return False, time.time() - start_time

def cleanup_captcha_images(image_paths):
    """Delete CAPTCHA image files once they are no longer needed."""
    for img_path in image_paths:
        try:
            if os.path.exists(img_path):
                os.remove(img_path)
                print(f"Deleted CAPTCHA image: {img_path}")
        except Exception as e:
            print(f"Failed to delete CAPTCHA image {img_path}: {e}")

def main(start_id=START_ID, end_id=END_ID, batch_size=BATCH_SIZE):
    """
    Main function to process batch files.

    Args:
        start_id (int, optional): ID to start processing from. Default is START_ID.
        end_id (int, optional): ID to end processing at. Default is END_ID.
        batch_size (int, optional): Size of each batch. Default is BATCH_SIZE.
    """
    print(f"Starting processing with configuration:")
    print(f"  Start ID: {start_id if start_id is not None else 'None (processing all)'}")
    print(f"  End ID: {end_id if end_id is not None else 'None (processing to the end)'}")
    print(f"  Batch size: {batch_size}")

    # Load the batch index
    batch_index = load_batch_index()
    if not batch_index:
        print("No batch index found or error loading index. Exiting.")
        return

    print(f"Loaded batch index with {len(batch_index['batches'])} batches")

    # Configure Chrome WebDriver
    chrome_options = Options()
    # Configure Chrome to download directly to our PDFS_FOLDER
    prefs = {
        "download.default_directory": ABSOLUTE_PDFS_FOLDER,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # Initialize the WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Determine which batches to process based on start_id and end_id
        batches_to_process = []

        if start_id is not None or end_id is not None:
            # Find batches that fall within the specified ID range
            for batch_info in batch_index['batches']:
                if (start_id is None or batch_info['end_id'] >= start_id) and \
                   (end_id is None or batch_info['start_id'] <= end_id):
                    batches_to_process.append(batch_info)
        else:
            # Process all batches that are not completed
            batches_to_process = [batch for batch in batch_index['batches'] 
                                 if batch['download_status'] != 'completed']

        print(f"Found {len(batches_to_process)} batches to process")

        # Variables for time estimation
        start_time_total = time.time()
        completed_entries = 0
        total_entries_to_process = 0
        
        # Count entries within the specified range for time estimation
        for batch_info in batches_to_process:
            batch_file = batch_info['filename']
            batch_data = load_batch(batch_file)
            if batch_data:
                entries_in_range = [
                    entry for entry in batch_data 
                    if entry.get('download_status') in ['not_processed', 'pending']
                    and (start_id is None or entry.get('id', 0) >= start_id)
                    and (end_id is None or entry.get('id', 0) <= end_id)
                ]
                total_entries_to_process += len(entries_in_range)
                
        print(f"Total entries to process within ID range: {total_entries_to_process}")
        
        total_processing_time = 0

        # Process each batch
        for batch_idx, batch_info in enumerate(batches_to_process):
            batch_id = batch_info['batch_id']
            batch_file = batch_info['filename']

            print(f"\n============================================================")
            print(f"Processing batch {batch_id} ({batch_idx+1}/{len(batches_to_process)}): {batch_file}")
            print(f"============================================================")

            # Load the batch data
            batch_data = load_batch(batch_file)
            if not batch_data:
                print(f"Error loading batch {batch_id}. Skipping.")
                continue

            # Update batch status to in_progress
            batch_info['download_status'] = 'in_progress'
            save_batch_index(batch_index)

            # Count entries in this batch that match our criteria
            entries_to_process = [
                entry for entry in batch_data 
                if entry.get('download_status') in ['not_processed', 'pending']
            ]

            # Filter by start_id and end_id if specified
            if start_id is not None or end_id is not None:
                entries_to_process = [
                    e for e in entries_to_process 
                    if (start_id is None or e.get('id', 0) >= start_id)
                    and (end_id is None or e.get('id', 0) <= end_id)
                ]

            # Skip if no entries to process in this batch
            if not entries_to_process:
                print(f"No entries to process in batch {batch_id} within the specified ID range.")
                continue

            print(f"Found {len(entries_to_process)} entries to process in batch {batch_id}")

            # Process each entry in the batch
            batch_completed = 0

            for i, entry in enumerate(batch_data):
                # Only process entries that need processing and meet ID criteria
                if (entry.get('download_status') in ['not_processed', 'pending'] and 
                    (start_id is None or entry.get('id', 0) >= start_id) and
                    (end_id is None or entry.get('id', 0) <= end_id)):

                    print(f"\n------------------------------------------------------------")
                    print(f"Processing {batch_completed+1}/{len(entries_to_process)} in batch {batch_id}: Entry ID {entry.get('id', 'unknown')}")

                    # Process the entry and get elapsed time
                    success, elapsed_time = process_entry(entry, driver)

                    if success:
                        batch_completed += 1
                        completed_entries += 1
                        total_processing_time += elapsed_time

                    # Save progress after each entry
                    save_batch(batch_data, batch_file)

                    # Calculate and display time estimates
                    if completed_entries > 0:
                        avg_time_per_entry = total_processing_time / completed_entries
                        remaining_entries = total_entries_to_process - completed_entries
                        estimated_remaining_time = avg_time_per_entry * remaining_entries

                        # Convert to hours, minutes, seconds
                        hours, remainder = divmod(estimated_remaining_time, 3600)
                        minutes, seconds = divmod(remainder, 60)

                        elapsed_total = time.time() - start_time_total
                        elapsed_hours, remainder = divmod(elapsed_total, 3600)
                        elapsed_minutes, elapsed_seconds = divmod(remainder, 60)

                        print(f"\nProgress: {completed_entries}/{total_entries_to_process} entries processed ({(completed_entries/total_entries_to_process)*100:.1f}%)")
                        print(f"Average processing time: {avg_time_per_entry:.2f} seconds per entry")
                        print(f"Elapsed time: {int(elapsed_hours)}h {int(elapsed_minutes)}m {int(elapsed_seconds)}s")
                        print(f"Estimated time remaining: {int(hours)}h {int(minutes)}m {int(seconds)}s")
                        print(f"Estimated completion: {datetime.datetime.now() + datetime.timedelta(seconds=estimated_remaining_time)}")

                    # Random delay between requests to avoid being blocked
                    delay = random.uniform(MIN_DELAY, MAX_DELAY)
                    print(f"Waiting {delay:.2f} seconds before next request...")
                    time.sleep(delay)

            # Check if all entries in the batch are fully processed (ignoring ID range filter)
            remaining_pending = sum(1 for e in batch_data if e.get('download_status') in ['not_processed', 'pending'])
            if remaining_pending == 0:
                batch_info['download_status'] = 'completed'
                print(f"Batch {batch_id} completed successfully.")
            else:
                # Only mark complete if we processed all entries in our filter range
                processed_in_range = sum(1 for e in batch_data 
                                         if (start_id is None or e.get('id', 0) >= start_id)
                                         and (end_id is None or e.get('id', 0) <= end_id))
                
                pending_in_range = sum(1 for e in batch_data 
                                      if e.get('download_status') in ['not_processed', 'pending']
                                      and (start_id is None or e.get('id', 0) >= start_id)
                                      and (end_id is None or e.get('id', 0) <= end_id))
                
                if pending_in_range == 0:
                    print(f"Batch {batch_id}: Processed all {processed_in_range} entries in the specified ID range.")
                    print(f"Batch {batch_id} still has {remaining_pending} entries pending outside the specified range.")
                else:
                    print(f"Batch {batch_id} has {pending_in_range} entries still pending in the specified ID range.")

            # Update batch index
            save_batch_index(batch_index)

    finally:
        # Close the browser
        driver.quit()

        # Print summary
        print("\nProcessing complete!")
        total_time = time.time() - start_time_total
        hours, remainder = divmod(total_time, 3600)
        minutes, seconds = divmod(remainder, 60)

        print(f"Total runtime: {int(hours)}h {int(minutes)}m {int(seconds)}s")
        print(f"Completed entries in this run: {completed_entries}")
        
        print(f"ID Range: {start_id or 'Beginning'} to {end_id or 'End'}")

        # Overall batch status
        batch_statuses = {
            'not_started': sum(1 for b in batch_index['batches'] if b['download_status'] == 'not_started'),
            'in_progress': sum(1 for b in batch_index['batches'] if b['download_status'] == 'in_progress'),
            'completed': sum(1 for b in batch_index['batches'] if b['download_status'] == 'completed')
        }

        print(f"Batch status summary:")
        print(f"  Not started: {batch_statuses['not_started']}")
        print(f"  In progress: {batch_statuses['in_progress']}")
        print(f"  Completed: {batch_statuses['completed']}")
        print(f"  Total batches: {len(batch_index['batches'])}")

if __name__ == "__main__":
    # Simply call main with the configured variables
    main()