import json
import os
import time
import base64
import random
import requests
import datetime
import glob
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from mistralai import Mistral
from pathlib import Path

# Constants
DATA_FILE = 'assets/combined_data.json'
IMAGES_FOLDER = 'assets/images'
PDFS_FOLDER = 'assets/pdfs'
MIN_DELAY = 1  # Minimum delay between requests (seconds)
MAX_DELAY = 2  # Maximum delay between requests (seconds)

# Ensure directories exist
Path(IMAGES_FOLDER).mkdir(parents=True, exist_ok=True)
Path(PDFS_FOLDER).mkdir(parents=True, exist_ok=True)

# Get absolute path for PDF downloads
ABSOLUTE_PDFS_FOLDER = os.path.abspath(PDFS_FOLDER)

def encode_image(image_path):
    """Encode the image to base64."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"Error: The file {image_path} was not found.")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def solve_captcha(image_path):
    """Use Mistral AI to solve the captcha."""
    # Getting the base64 string
    base64_image = encode_image(image_path)
    if not base64_image:
        return None

    try:
        # Retrieve the API key from environment variables
        api_key = "k9yk782QzRn2DynfJSGLjFfzGauIroLz"
        if not api_key:
            raise ValueError("MISTRAL_API_KEY not found in environment variables")

        # Specify model
        model = "pixtral-12b-2409"

        # Initialize the Mistral client
        client = Mistral(api_key=api_key)

        # Define the messages for the chat
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "This is a CAPTCHA image. Please tell me only the characters or numbers shown in this image. Return only the exact CAPTCHA text, nothing else."
                    },
                    {
                        "type": "image_url",
                        "image_url": f"data:image/jpeg;base64,{base64_image}" 
                    }
                ]
            }
        ]

        # Get the chat response
        chat_response = client.chat.complete(
            model=model,
            messages=messages
        )

        # Extract the content of the response
        captcha_text = chat_response.choices[0].message.content
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

def load_data():
    """Load the combined data and initialize status field if needed."""
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as file:
            data = json.load(file)
            
        # Add status field if not present or convert "not_processed" to "pending"
        modified = False
        for entry in data:
            if 'status' not in entry:
                entry['status'] = 'pending'
                modified = True
            elif entry['status'] == 'not_processed':
                entry['status'] = 'pending'
                modified = True
                
        # If we modified the data, save it back
        if modified:
            save_data(data)
            
        # Sort data by ID to process in sequence: 1, 2, 3, etc.
        data = sorted(data, key=lambda x: x.get('id', float('inf')))
            
        return data
    except Exception as e:
        print(f"Error loading data: {e}")
        return []

def save_data(data):
    """Save data back to the JSON file."""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving data: {e}")
        return False

def process_entry(entry, driver):
    """Process a single entry: fetch captcha, solve it, and download PDF."""
    entry_id = entry.get('id', 'unknown')
    url = entry.get('download_url')
    start_time = time.time()
    
    if not url:
        print(f"Entry {entry_id}: No download URL found")
        entry['status'] = 'error_no_url'
        return False, 0
    
    try:
        print(f"Processing entry {entry_id}: Navigating to {url}")
        print(f"Start time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        driver.get(url)
        
        # Variables for CAPTCHA retry logic
        captcha_solved = False
        captcha_attempts = 0
        max_captcha_attempts = 3  # Initial attempt + 2 retries
        
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
                            entry['status'] = 'error_captcha_reload_failed'
                            return False, time.time() - start_time
                    else:
                        entry['status'] = 'error_captcha_unsolved'
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
                                entry['status'] = 'error_captcha_reload_failed'
                                return False, time.time() - start_time
                        else:
                            entry['status'] = 'error_invalid_captcha'
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
                            entry['status'] = 'error_captcha_reload_failed'
                            return False, time.time() - start_time
                    else:
                        print(f"Entry {entry_id}: No PDF downloaded after all attempts")
                        entry['status'] = 'error_no_download'
                        return False, time.time() - start_time
                
                # Store the actual downloaded filename in the entry
                pdf_path = f"{PDFS_FOLDER}/{downloaded_file}"
                entry['pdf_file_path'] = pdf_path
                entry['status'] = 'completed'
                
                elapsed_time = time.time() - start_time
                print(f"Entry {entry_id}: Processed successfully in {elapsed_time:.2f} seconds")
                print(f"End time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
                    entry['status'] = 'error_element_not_found'
                    return False, time.time() - start_time
            
    except Exception as e:
        print(f"Entry {entry_id}: Processing error - {e}")
        entry['status'] = f'error_processing'
        return False, time.time() - start_time

def main():
    """Main function to process all entries in the data file."""
    # Load the data
    data = load_data()
    if not data:
        print("No data found or error loading data. Exiting.")
        return

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
        # Count pending entries
        pending_entries = [entry for entry in data if entry.get('status') in ['pending', 'not_processed']]
        total_pending = len(pending_entries)
        if total_pending == 0:
            print("No pending entries to process. Exiting.")
            return
            
        print(f"Found {total_pending} pending entries to process.")
        
        # Variables for time estimation
        start_time_total = time.time()
        completed_count = 0
        total_processing_time = 0
        
        # Process each entry that's still pending or not_processed
        for i, entry in enumerate(data):
            if entry.get('status') in ['pending', 'not_processed']:
                print(f"\n------------------------------------------------------------")
                print(f"Processing {completed_count+1}/{total_pending}: Entry ID {entry.get('id', 'unknown')}")
                
                # Process the entry and get elapsed time
                success, elapsed_time = process_entry(entry, driver)
                
                if success:
                    completed_count += 1
                    total_processing_time += elapsed_time
                
                # Save progress after each entry
                save_data(data)
                
                # Calculate and display time estimates
                if completed_count > 0:
                    avg_time_per_entry = total_processing_time / completed_count
                    remaining_entries = total_pending - completed_count
                    estimated_remaining_time = avg_time_per_entry * remaining_entries
                    
                    # Convert to hours, minutes, seconds
                    hours, remainder = divmod(estimated_remaining_time, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    elapsed_total = time.time() - start_time_total
                    elapsed_hours, remainder = divmod(elapsed_total, 3600)
                    elapsed_minutes, elapsed_seconds = divmod(remainder, 60)
                    
                    print(f"\nProgress: {completed_count}/{total_pending} entries processed ({(completed_count/total_pending)*100:.1f}%)")
                    print(f"Average processing time: {avg_time_per_entry:.2f} seconds per entry")
                    print(f"Elapsed time: {int(elapsed_hours)}h {int(elapsed_minutes)}m {int(elapsed_seconds)}s")
                    print(f"Estimated time remaining: {int(hours)}h {int(minutes)}m {int(seconds)}s")
                    print(f"Estimated completion: {datetime.datetime.now() + datetime.timedelta(seconds=estimated_remaining_time)}")
                
                # Random delay between requests to avoid being blocked
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                print(f"Waiting {delay:.2f} seconds before next request...")
                time.sleep(delay)
            elif i < len(data) - 1:  # Only print skip message if not the last item
                print(f"Skipping already processed entry ID {entry.get('id', 'unknown')} with status: {entry.get('status')}")
    
    finally:
        # Close the browser
        driver.quit()
        
        # Save final state
        save_data(data)
        
        # Print summary
        completed = sum(1 for entry in data if entry.get('status') == 'completed')
        pending = sum(1 for entry in data if entry.get('status') == 'pending')
        errors = sum(1 for entry in data if entry.get('status', '').startswith('error'))
        
        total_time = time.time() - start_time_total
        hours, remainder = divmod(total_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        print("\nProcessing complete!")
        print(f"Total runtime: {int(hours)}h {int(minutes)}m {int(seconds)}s")
        print(f"Total entries: {len(data)}")
        print(f"Completed: {completed}")
        print(f"Pending: {pending}")
        print(f"Errors: {errors}")

if __name__ == "__main__":
    main()
