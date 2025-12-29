import aspose.pdf as ap
import os
from pathlib import Path

try:
	from pypdf import PdfReader, PdfWriter
except Exception:  # pragma: no cover
	PdfReader = None
	PdfWriter = None

input_pdf = "C:/Users/ashat/persnal/projects/python-projects/voter-shield-altenative-approach/pdf/2025-EROLLGEN-S22-116-FinalRoll-Revision1-ENG-244-WI.pdf"
output_md = "C:/Users/ashat/persnal/projects/python-projects/voter-shield-altenative-approach/output/convert_pdf_to_md.md"  # Fixed variable name

license_path = os.environ.get(
	"ASPOSE_PDF_LICENSE_PATH",
	"C:/Users/ashat/persnal/projects/python-projects/voter-shield-altenative-approach/Aspose.PDF.lic",
)
if Path(license_path).exists():
	ap.License().set_license(license_path)
# Open PDF document
document = ap.Document(input_pdf)

# Instantiate markdown Save options
save_options = getattr(ap, "MarkdownSaveOptions", None)
if save_options is None:
	save_options = ap.MdSaveOptions
save_options = save_options()

Path(output_md).parent.mkdir(parents=True, exist_ok=True)

# Save the Markdown document
try:
	document.save(output_md, save_options)
except RuntimeError as exc:
	message = str(exc)
	if "evaluation mode" not in message and "At most 4 elements" not in message:
		raise

	if PdfReader is None or PdfWriter is None:
		raise RuntimeError(
			"Aspose.PDF is running in evaluation mode and this PDF exceeds the limit. "
			"Install 'pypdf' to enable automatic 'first N pages' fallback, or provide an Aspose license."
		) from exc

	max_pages = int(os.environ.get("PDF_TO_MD_MAX_PAGES", "4"))
	input_path = Path(input_pdf)
	subset_pdf = input_path.with_name(f"{input_path.stem}__first_{max_pages}_pages.pdf")

	reader = PdfReader(str(input_path))
	writer = PdfWriter()
	for page in reader.pages[:max_pages]:
		writer.add_page(page)
	with open(subset_pdf, "wb") as f:
		writer.write(f)

	subset_doc = ap.Document(str(subset_pdf))
	subset_doc.save(output_md, save_options)