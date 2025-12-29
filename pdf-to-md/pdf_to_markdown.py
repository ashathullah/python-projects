#!/usr/bin/env python3
"""
PDF to Markdown Converter
Converts PDF files to Markdown format with text extraction and basic formatting.
"""

import sys
import os
import argparse
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF (fitz) is not installed.")
    print("Please install it using: pip install pymupdf")
    sys.exit(1)

try:
    import pytesseract
    from PIL import Image
    import io
    OCR_AVAILABLE = True
    
    # Configure tesseract path for Windows
    if sys.platform == 'win32':
        # Common Tesseract installation paths on Windows
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', ''))
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break
except ImportError:
    OCR_AVAILABLE = False


def extract_text_with_ocr(page):
    """
    Extract text from page using OCR.
    
    Args:
        page: PyMuPDF page object
        
    Returns:
        str: Extracted text using OCR
    """
    if not OCR_AVAILABLE:
        return ""
    
    try:
        # Render page to image
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scale for better OCR
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        
        # Perform OCR
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        print(f"  Warning: OCR failed - {str(e)}")
        return ""


def extract_text_from_pdf(pdf_path, use_ocr=False, verbose=False):
    """
    Extract text from PDF file with page structure.
    
    Args:
        pdf_path (str): Path to the PDF file
        use_ocr (bool): Force OCR usage for image-based PDFs
        verbose (bool): Print detailed extraction information
        
    Returns:
        str: Extracted text in markdown format
    """
    try:
        doc = fitz.open(pdf_path)
        markdown_content = []
        
        # Add document title
        pdf_name = Path(pdf_path).stem
        markdown_content.append(f"# {pdf_name}\n")
        
        if verbose:
            print(f"Total pages: {len(doc)}")
        
        empty_pages = 0
        
        # Extract text from each page
        for page_num, page in enumerate(doc, start=1):
            if verbose:
                print(f"Processing page {page_num}/{len(doc)}...", end=' ')
            
            markdown_content.append(f"\n## Page {page_num}\n")
            
            # Try multiple extraction methods
            text = ""
            
            # Method 1: Standard text extraction
            text = page.get_text("text")
            
            # Method 2: Try "blocks" method if text is empty
            if not text.strip():
                blocks = page.get_text("blocks")
                text_blocks = [block[4] for block in blocks if len(block) > 4]
                text = '\n\n'.join(text_blocks)
            
            # Method 3: Try OCR if still empty and OCR is available
            if not text.strip() and (use_ocr or OCR_AVAILABLE):
                if verbose:
                    print("(using OCR)...", end=' ')
                text = extract_text_with_ocr(page)
            
            # Clean up and format text
            if text.strip():
                lines = text.split('\n')
                formatted_lines = []
                
                for line in lines:
                    line = line.strip()
                    if line:
                        formatted_lines.append(line)
                
                # Join lines with proper spacing
                page_text = '\n\n'.join(formatted_lines)
                markdown_content.append(page_text)
                
                if verbose:
                    print(f"✓ ({len(formatted_lines)} lines)")
            else:
                empty_pages += 1
                markdown_content.append("*[No text content detected on this page]*")
                if verbose:
                    print("✗ (empty)")
        
        doc.close()
        
        if verbose:
            print(f"\nExtraction complete: {len(doc) - empty_pages}/{len(doc)} pages with content")
            if empty_pages > 0 and not OCR_AVAILABLE:
                print(f"Note: {empty_pages} pages were empty. Install tesseract-ocr for image-based PDF support.")
        
        return '\n'.join(markdown_content)
        
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")


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


def convert_pdf_to_markdown(pdf_path, output_path=None, use_ocr=False, verbose=False):
    """
    Convert PDF file to Markdown.
    
    Args:
        pdf_path (str): Path to the PDF file
        output_path (str, optional): Path for the output markdown file
        use_ocr (bool): Force OCR usage for image-based PDFs
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
    
    # Extract text and convert to markdown
    markdown_content = extract_text_from_pdf(pdf_path, use_ocr=use_ocr, verbose=verbose)
    
    # Save to file
    save_markdown(markdown_content, output_path)


def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Convert PDF files to Markdown format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_to_markdown.py document.pdf
  python pdf_to_markdown.py scanned.pdf --ocr -v
        """
    )
    
    parser.add_argument('pdf_file', help='Path to the PDF file to convert')
    parser.add_argument('-o', '--output', help='Output markdown file path (optional)')
    parser.add_argument('--ocr', action='store_true', 
                       help='Use OCR for image-based PDFs (requires tesseract)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Show detailed extraction progress')
    
    args = parser.parse_args()
    
    try:
        convert_pdf_to_markdown(args.pdf_file, args.output, 
                              use_ocr=args.ocr, verbose=args.verbose)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
