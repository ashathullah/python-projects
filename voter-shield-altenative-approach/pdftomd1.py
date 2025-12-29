import os
from marker.convert import convert_single_pdf
from marker.models import load_all_models
from marker.output import save_markdown

def convert_to_md(pdf_path, output_dir):
    # Load the necessary models (only needs to run once)
    model_lst = load_all_models()
    
    # Convert the PDF
    full_text, images, out_meta = convert_single_pdf(pdf_path, model_lst)
    
    # Define the output filename
    fname = os.path.basename(pdf_path).replace(".pdf", "")
    
    # Save the markdown and any extracted images
    save_markdown(output_dir, fname, full_text, images, out_meta)
    print(f"Conversion complete! Files saved to: {output_dir}")

# Usage
convert_to_md("C:/Users/ashat/persnal/projects/python-projects/voter-shield-altenative-approach/pdf/2025-EROLLGEN-S22-116-FinalRoll-Revision1-ENG-244-WI__first_4_pages.pdf", "./output_folder")