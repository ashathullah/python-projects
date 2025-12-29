#!/usr/bin/env python3
"""
PDF to Markdown Converter using Browser OCR
Uses Chrome's built-in PDF viewer and OCR capabilities to extract text from PDFs.
"""

import sys
import os
import time
import argparse
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
except ImportError:
    print("Error: Selenium is not installed.")
    print("Please install it using: pip install selenium")
    sys.exit(1)


def setup_chrome_driver(headless=False):
    """
    Setup Chrome WebDriver with appropriate options.
    
    Args:
        headless (bool): Run Chrome in headless mode
        
    Returns:
        webdriver.Chrome: Configured Chrome driver
    """
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument('--headless=new')
    
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Enable accessibility features for OCR
    chrome_options.add_argument('--force-renderer-accessibility')
    chrome_options.add_argument('--enable-accessibility-object-model')
    
    # Enable PDF viewer with OCR
    chrome_options.add_experimental_option('prefs', {
        'plugins.always_open_pdf_externally': False,
        'download.prompt_for_download': False,
        'download.default_directory': os.getcwd(),
        'profile.default_content_setting_values.automatic_downloads': 1,
        'accessibility.pdf_ocr_always_active': True,
    })
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error: Failed to start Chrome WebDriver - {str(e)}")
        print("\nMake sure Chrome and ChromeDriver are installed:")
        print("- Chrome: https://www.google.com/chrome/")
        print("- ChromeDriver: Download automatically via selenium or manually from:")
        print("  https://chromedriver.chromium.org/")
        sys.exit(1)


def extract_text_from_pdf_browser(pdf_path, driver, verbose=False):
    """
    Extract text from PDF using Chrome's built-in viewer and OCR.
    
    Args:
        pdf_path (str): Path to the PDF file
        driver: Selenium WebDriver instance
        verbose (bool): Print detailed extraction information
        
    Returns:
        str: Extracted text in markdown format
    """
    # Convert to absolute path and file URL
    abs_path = os.path.abspath(pdf_path)
    file_url = f"file:///{abs_path.replace(os.sep, '/')}"
    
    if verbose:
        print(f"Opening PDF in Chrome: {file_url}")
    
    # Load PDF in Chrome
    driver.get(file_url)
    
    # Wait for PDF to load
    if verbose:
        print("Waiting for PDF to load...")
    time.sleep(3)
    
    markdown_content = []
    pdf_name = Path(pdf_path).stem
    markdown_content.append(f"# {pdf_name}\n")
    
    try:
        # Switch to PDF viewer embed element
        if verbose:
            print("Locating PDF viewer...")
        
        try:
            embed = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "embed"))
            )
            if verbose:
                print("PDF viewer found")
        except:
            if verbose:
                print("No embed element found, using body")
        
        # Scroll through the entire PDF to trigger OCR on all pages
        if verbose:
            print("Scrolling through PDF to trigger OCR (this may take a minute)...")
        
        body = driver.find_element(By.TAG_NAME, "body")
        
        # Scroll down multiple times to load all pages
        for i in range(60):  # Scroll 60 times to cover most PDFs
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(0.5)
            if verbose and (i + 1) % 10 == 0:
                print(f"  Scrolled {i + 1} pages...")
        
        # Scroll back to top
        body.send_keys(Keys.HOME)
        time.sleep(1)
        
        if verbose:
            print("Waiting 30 seconds for OCR to complete...")
        time.sleep(30)
        
        # Select all text using Ctrl+A
        if verbose:
            print("Selecting all text...")
        
        actions = ActionChains(driver)
        
        # Click on body first to ensure focus
        body.click()
        time.sleep(0.5)
        
        # Use Ctrl+A to select all
        if sys.platform == 'darwin':  # macOS
            actions.key_down(Keys.COMMAND).send_keys('a').key_up(Keys.COMMAND).perform()
        else:  # Windows/Linux
            actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
        
        time.sleep(2)
        
        # Copy selected text using Ctrl+C
        if verbose:
            print("Copying text...")
        
        if sys.platform == 'darwin':
            actions.key_down(Keys.COMMAND).send_keys('c').key_up(Keys.COMMAND).perform()
        else:
            actions.key_down(Keys.CONTROL).send_keys('c').key_up(Keys.CONTROL).perform()
        
        time.sleep(2)
        
        # Get clipboard content using JavaScript
        if verbose:
            print("Reading clipboard...")
        
        # Try to get clipboard content via JavaScript
        # Note: This requires clipboard permissions
        text = driver.execute_script("""
            return new Promise((resolve, reject) => {
                navigator.clipboard.readText()
                    .then(text => resolve(text))
                    .catch(err => resolve(''));
            });
        """)
        
        if not text:
            if verbose:
                print("Warning: Clipboard reading failed, trying alternative method...")
            
            # Alternative: Try to execute copy command and paste into a textarea
            driver.execute_script("""
                var textarea = document.createElement('textarea');
                textarea.id = 'copypaste';
                document.body.appendChild(textarea);
                textarea.focus();
            """)
            
            time.sleep(0.5)
            
            # Paste using Ctrl+V
            if sys.platform == 'darwin':
                actions.key_down(Keys.COMMAND).send_keys('v').key_up(Keys.COMMAND).perform()
            else:
                actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
            
            time.sleep(0.5)
            
            # Get text from textarea
            text = driver.execute_script("""
                var textarea = document.getElementById('copypaste');
                return textarea ? textarea.value : '';
            """)
        
        if text.strip():
            # Format text into markdown
            lines = text.split('\n')
            formatted_lines = []
            
            for line in lines:
                line = line.strip()
                if line:
                    formatted_lines.append(line)
            
            # Join with proper spacing
            content = '\n\n'.join(formatted_lines)
            markdown_content.append(content)
            
            if verbose:
                print(f"✓ Extracted {len(formatted_lines)} lines of text")
        else:
            markdown_content.append("*[No text content could be extracted]*")
            if verbose:
                print("✗ No text extracted")
        
    except Exception as e:
        print(f"Warning: Error during text extraction - {str(e)}")
        markdown_content.append(f"*[Error during extraction: {str(e)}]*")
    
    return '\n'.join(markdown_content)


def save_markdown(content, output_path):
    """
    Save markdown content to file.
    
    Args:
        content (str): Markdown content
        output_path (str): Path to save the markdown file
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Successfully saved markdown to: {output_path}")
    except Exception as e:
        raise Exception(f"Error saving markdown file: {str(e)}")


def convert_pdf_to_markdown(pdf_path, output_path=None, headless=False, verbose=False):
    """
    Convert PDF file to Markdown using Chrome browser.
    
    Args:
        pdf_path (str): Path to the PDF file
        output_path (str, optional): Path for the output markdown file
        headless (bool): Run Chrome in headless mode
        verbose (bool): Print detailed extraction information
    """
    # Validate input file
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    if not pdf_path.lower().endswith('.pdf'):
        raise ValueError("Input file must be a PDF file")
    
    # Determine output path
    if output_path is None:
        output_path = Path(pdf_path).with_suffix('.md')
    else:
        output_path = Path(output_path)
        if output_path.suffix.lower() != '.md':
            output_path = output_path.with_suffix('.md')
    
    print(f"Converting: {pdf_path}")
    print(f"Output to: {output_path}")
    
    # Setup Chrome driver
    driver = setup_chrome_driver(headless=headless)
    
    try:
        # Extract text using browser
        markdown_content = extract_text_from_pdf_browser(pdf_path, driver, verbose=verbose)
        
        # Save to file
        save_markdown(markdown_content, output_path)
        
    finally:
        # Close browser
        driver.quit()
        if verbose:
            print("Browser closed")


def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Convert PDF files to Markdown using Chrome browser OCR',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_to_markdown_browser.py document.pdf
  python pdf_to_markdown_browser.py document.pdf -o output.md
  python pdf_to_markdown_browser.py scanned.pdf --headless -v
        """
    )
    
    parser.add_argument('pdf_file', help='Path to the PDF file to convert')
    parser.add_argument('-o', '--output', help='Output markdown file path (optional)')
    parser.add_argument('--headless', action='store_true',
                       help='Run Chrome in headless mode (no visible window)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Show detailed extraction progress')
    
    args = parser.parse_args()
    
    try:
        convert_pdf_to_markdown(args.pdf_file, args.output,
                              headless=args.headless, verbose=args.verbose)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
