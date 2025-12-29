#!/usr/bin/env python3
"""
PDF to Markdown Converter using OCR
Converts PDF pages to images and uses Tesseract OCR for text extraction.
"""

import sys
import os
import argparse
from pathlib import Path

try:
    from pdf2image import convert_from_path
    import pytesseract
    from PIL import Image
except ImportError as e:
    print(f"Error: Required library not installed - {e}")
    print("\nPlease install required libraries:")
    print("pip install pdf2image pillow pytesseract")
    print("\nAlso install poppler:")
    print("Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases/")
    print("Extract and add bin folder to PATH")
    sys.exit(1)


def setup_tesseract():
    """Configure Tesseract OCR path for Windows."""
    if sys.platform == 'win32':
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                return True
        print("Warning: Tesseract not found in standard locations")
        print("Make sure it's installed at: C:\\Program Files\\Tesseract-OCR\\")
        return False
    return True


def extract_text_from_pdf_with_ocr(pdf_path, poppler_path=None, language='tam+eng', verbose=False):
    """
    Extract text from PDF using OCR on each page.
    
    Args:
        pdf_path (str): Path to the PDF file
        poppler_path (str): Path to poppler bin folder (Windows)
        language (str): Tesseract language code (e.g., 'tam+eng' for Tamil and English)
        verbose (bool): Print detailed extraction information
        
    Returns:
        str: Extracted text in markdown format
    """
    setup_tesseract()
    
    if verbose:
        print(f"Converting PDF to images...")
        print(f"OCR Language: {language}")
    
    try:
        # Convert PDF pages to images
        if poppler_path and os.path.exists(poppler_path):
            images = convert_from_path(pdf_path, poppler_path=poppler_path, dpi=300)
        else:
            images = convert_from_path(pdf_path, dpi=300)
        
        if verbose:
            print(f"Total pages: {len(images)}")
        
    except Exception as e:
        raise Exception(f"Error converting PDF to images: {str(e)}\n"
                       "Make sure poppler is installed and accessible.")
    
    markdown_content = []
    pdf_name = Path(pdf_path).stem
    markdown_content.append(f"# {pdf_name}\n")
    
    # Process each page
    for page_num, image in enumerate(images, start=1):
        if verbose:
            print(f"Processing page {page_num}/{len(images)}...", end=' ')
        
        markdown_content.append(f"\n## Page {page_num}\n")
        
        try:
            # Perform OCR on the image with specified language
            text = pytesseract.image_to_string(image, lang=language)
            
            if text.strip():
                # Format text
                lines = text.split('\n')
                formatted_lines = []
                
                for line in lines:
                    line = line.strip()
                    if line:
                        formatted_lines.append(line)
                
                if formatted_lines:
                    page_text = '\n\n'.join(formatted_lines)
                    markdown_content.append(page_text)
                    
                    if verbose:
                        print(f"✓ ({len(formatted_lines)} lines)")
                else:
                    markdown_content.append("*[No text detected on this page]*")
                    if verbose:
                        print("✗ (empty)")
            else:
                markdown_content.append("*[No text detected on this page]*")
                if verbose:
                    print("✗ (empty)")
                    
        except Exception as e:
            markdown_content.append(f"*[Error processing page: {str(e)}]*")
            if verbose:
                print(f"✗ (error: {str(e)})")
    
    if verbose:
        print("\nOCR extraction complete!")
    
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


def convert_pdf_to_markdown(pdf_path, output_path=None, poppler_path=None, language='tam+eng', verbose=False):
    """
    Convert PDF file to Markdown using OCR.
    
    Args:
        pdf_path (str): Path to the PDF file
        output_path (str, optional): Path for the output markdown file
        poppler_path (str, optional): Path to poppler bin folder
        language (str): Tesseract language code (default: 'tam+eng' for Tamil and English)
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
    
    # Extract text using OCR
    markdown_content = extract_text_from_pdf_with_ocr(pdf_path, poppler_path, language, verbose)
    
    # Save to file
    save_markdown(markdown_content, output_path)


def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Convert PDF files to Markdown using OCR (Tesseract)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Tamil and English (default)
  python pdf_to_markdown_ocr.py document.pdf -v
  
  # Tamil only
  python pdf_to_markdown_ocr.py document.pdf -l tam -v
  
  # English only
  python pdf_to_markdown_ocr.py document.pdf -l eng -v
  
  # With poppler path
  python pdf_to_markdown_ocr.py document.pdf --poppler "C:\\poppler\\bin" -v

Requirements:
  - Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
  - Tamil language data: Install during Tesseract setup or download tam.traineddata
  - Poppler: https://github.com/oschwartz10612/poppler-windows/releases/
        """
    )
    
    parser.add_argument('pdf_file', help='Path to the PDF file to convert')
    parser.add_argument('-o', '--output', help='Output markdown file path (optional)')
    parser.add_argument('-p', '--poppler', 
                       default=r'C:\Program Files\poppler-25.12.0\Library\bin',
                       help='Path to poppler bin folder (default: C:\\Program Files\\poppler-25.12.0\\Library\\bin)')
    parser.add_argument('-l', '--language', default='tam',
                       help='Tesseract language code (default: tam for Tamil). Use "eng" for English, "tam+eng" for both')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Show detailed extraction progress')
    
    args = parser.parse_args()
    
    try:
        convert_pdf_to_markdown(args.pdf_file, args.output,
                              poppler_path=args.poppler, language=args.language,
                              verbose=args.verbose)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
