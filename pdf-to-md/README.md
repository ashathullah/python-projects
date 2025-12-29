# PDF to Markdown Converter

A Python script to convert PDF files to Markdown format with text extraction and basic formatting.

## Features

- Extract text from PDF files
- Convert to Markdown format with page structure
- Preserve document hierarchy
- Simple command-line interface
- Support for custom output paths

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

Or install PyMuPDF directly:

```bash
pip install pymupdf
```

## Usage

### Basic conversion:

```bash
python pdf_to_markdown.py document.pdf
```

This creates `document.md` in the same directory.

### Specify output file:

```bash
python pdf_to_markdown.py document.pdf -o output.md
```

### Convert file from pdf folder:

```bash
python pdf_to_markdown.py pdf/document.pdf -o markdown/document.md
```

## Command-line Options

- `pdf_file` - Path to the PDF file to convert (required)
- `-o, --output` - Output markdown file path (optional)

## Examples

```bash
# Convert a single PDF
python pdf_to_markdown.py report.pdf

# Convert with custom output name
python pdf_to_markdown.py report.pdf -o report_converted.md

# Convert PDF from specific folder
python pdf_to_markdown.py pdf/annual_report.pdf -o markdown/annual_report.md
```

## Output Format

The generated Markdown file includes:
- Document title (from PDF filename)
- Page-by-page structure
- Extracted text with basic formatting
- Page number headers

## Browser-Based Extraction (Alternative)

For PDFs that don't extract well with PyMuPDF, use the browser-based version:

```bash
python pdf_to_markdown_browser.py document.pdf -v
```

This uses Chrome's built-in PDF viewer and OCR. Features:
- Uses Chrome's native PDF rendering and text extraction
- Better for scanned or image-based PDFs
- Requires Chrome browser and Selenium
- Can run in headless mode: `--headless`

```bash
# Install additional dependency
pip install selenium

# Use browser extraction
python pdf_to_markdown_browser.py pdf/document.pdf -v

# Run in background (headless)
python pdf_to_markdown_browser.py document.pdf --headless
```

## Requirements

- Python 3.6+
- PyMuPDF (fitz)
- Selenium (for browser-based extraction)
- Google Chrome (for browser-based extraction)

## License

MIT License
