const fs = require('fs');
const path = require('path');
const pdf = require('pdf-parse');

// Use path.join or forward slashes to avoid Windows path issues
const pdffile = 'C:/Users/ashat/persnal/projects/python-projects/voter-shield-altenative-approach/pdf/2025-EROLLGEN-S22-116-FinalRoll-Revision1-ENG-244-WI.pdf';

async function extractText() {
    try {
        if (!fs.existsSync(pdffile)) {
            console.error("File not found check your path:", pdffile);
            return;
        }

        const dataBuffer = fs.readFileSync(pdffile);

        // Some versions of Node require calling the default export
        // We use a safe check here
        const parse = typeof pdf === 'function' ? pdf : pdf.default;

        const data = await parse(dataBuffer);

        console.log("--- Extraction Successful ---");
        console.log("Pages found:", data.numpages);
        console.log("Text Content:\n", data.text);

    } catch (err) {
        console.error("Error parsing PDF:", err);
    }
}

extractText();