import re
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, KeepInFrame
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Register your Tamil font from the same directory.
pdfmetrics.registerFont(TTFont('TamilFont', 'TiroTamil-Regular.ttf'))

def insert_zero_width_space(text):
    """
    Insert zero-width spaces between digits and letters to help break
    up very long strings for better wrapping in Tamil.
    """
    zws = "\u200b"
    text = re.sub(r'(\d)([^\d\s])', lambda m: m.group(1) + zws + m.group(2), text)
    text = re.sub(r'([^\d\s])(\d)', lambda m: m.group(1) + zws + m.group(2), text)
    return text

# 1. Read the text file and group addresses until a line contains "Phone".
input_file = "nomination-address.txt"
addresses = []
current_address_lines = []

with open(input_file, "r", encoding="utf-8") as file:
    for line in file:
        stripped_line = line.strip()
        if not stripped_line:
            continue
        current_address_lines.append(stripped_line)
        # Use "phone" (case-insensitive) to mark the end of an address.
        if "phone" in stripped_line.lower():
            address = "\n".join(current_address_lines)
            addresses.append(address)
            current_address_lines = []

# Add any remaining lines as an address.
if current_address_lines:
    addresses.append("\n".join(current_address_lines))

# Print the number of address entries processed.
print(f"Number of addresses processed: {len(addresses)}")

# 2. Pair addresses for a two-column layout.
table_data = []
for i in range(0, len(addresses), 2):
    first_address = addresses[i]
    second_address = addresses[i+1] if (i+1) < len(addresses) else ""
    table_data.append([first_address, second_address])

# 3. Set up the PDF document.
pdf_file = "addresses.pdf"
doc = SimpleDocTemplate(pdf_file, pagesize=letter)
styles = getSampleStyleSheet()

# 4. Create a Paragraph style using the registered Tamil font.
custom_style = ParagraphStyle(
    'Custom',
    parent=styles['Normal'],
    fontName='TamilFont',  # Must match the registered font name.
    fontSize=10,
    leading=12,
    wordWrap='CJK'
)

# 5. Process each address for the table.
formatted_data = []
cell_max_height = 600  # Maximum height (points) per cell; adjust if needed.

for row in table_data:
    formatted_row = []
    for cell in row:
        # Insert zero-width spaces for improved wrapping.
        cell = insert_zero_width_space(cell)
        # Replace newlines with <br /> tags for the Paragraph.
        cell = cell.replace("\n", "<br />")
        para = Paragraph(cell, custom_style)
        cell_width = doc.width / 2.0
        # KeepInFrame with 'shrink' mode scales content down if necessary.
        kif = KeepInFrame(cell_width, cell_max_height, [para], mode='shrink')
        formatted_row.append(kif)
    formatted_data.append(formatted_row)

# 6. Create the table with reduced padding.
table = Table(formatted_data, colWidths=[doc.width/2.0, doc.width/2.0])
table.setStyle(TableStyle([
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
    ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
    ('LEFTPADDING', (0, 0), (-1, -1), 2),
    ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ('TOPPADDING', (0, 0), (-1, -1), 2),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
]))

# 7. Build the PDF.
doc.build([table])
print(f"PDF file '{pdf_file}' created successfully!")
