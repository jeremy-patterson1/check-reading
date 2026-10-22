# check-reader

A small cross-platform Python tool that OCRs PDF checks and exports the useful
fields to CSV and JSON:

- date
- payee
- amount
- check number
- memo
- bank

It runs entirely on your machine with local Tesseract OCR. Account and routing
numbers are not written to the exports, and raw OCR text is never saved.

## Requirements

- Python 3.10+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) 5.x
- The Python packages in `pyproject.toml` (PyMuPDF, pytesseract, Pillow)

### Install Tesseract

**Linux (Debian/Ubuntu):**

```bash
sudo apt install tesseract-ocr
```

**Windows:** install the UB Mannheim build from
<https://github.com/UB-Mannheim/tesseract/wiki> and make sure `tesseract.exe`
is on `PATH`. If you cannot change `PATH`, point the tool at the executable:

```bat
set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

PowerShell:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Poppler is not required; PyMuPDF renders the PDF pages directly.

## Install the Python package

**Linux/macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

**Windows (PowerShell):**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

If PowerShell blocks activation, use Command Prompt instead:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -e ".[dev]"
```

## Put checks in `checks/`

Put the PDFs you want to process in `checks/`. The folder is ready, but real
checks are deliberately ignored by git:

```text
checks/
```

You can also run the bundled examples without copying anything:

```bash
python -m check_reader --input examples
```

Or run one file:

```bash
python -m check_reader examples/demo_check_1.pdf
```

After installation, the equivalent command is:

```bash
check-reader --input checks --output out
```

## Example run

```bash
python -m check_reader examples/demo_check_1.pdf
```

Output:

```text
[1/1] Reading examples/demo_check_1.pdf
  page 1: date='2026-09-14' payee='Acme Office Supply' amount='124.50' check_number='1042' memo='Invoice 1042' bank='FIRST NATIONAL DEMO BANK'
Wrote 1 check(s) to out/checks.csv and out/checks.json
Used Tesseract 5.5.0
```

`out/checks.csv`:

```csv
source,page,date,payee,amount,check_number,memo,bank,notes
examples/demo_check_1.pdf,1,2026-09-14,Acme Office Supply,124.50,1042,Invoice 1042,FIRST NATIONAL DEMO BANK,
```

`out/checks.json`:

```json
[
  {
    "source": "examples/demo_check_1.pdf",
    "page": 1,
    "date": "2026-09-14",
    "payee": "Acme Office Supply",
    "amount": "124.50",
    "check_number": "1042",
    "memo": "Invoice 1042",
    "bank": "FIRST NATIONAL DEMO BANK",
    "notes": ""
  }
]
```

## Options

```text
usage: check-reader [-h] [-i INPUT] [-o OUTPUT] [--dpi DPI] [--lang LANG] [input]

input                 PDF file or folder of PDFs (default: checks)
-i, --input INPUT     PDF file or folder of PDFs (default: checks)
-o, --output OUTPUT   folder for checks.csv and checks.json (default: out)
--dpi DPI             render resolution used for OCR (default: 300)
--lang LANG           Tesseract language code (default: eng)
```

PDFs are searched recursively when the input is a folder. Each PDF page is
treated as one check, and one row is written per page.

## What is exported

- `out/checks.csv` — UTF-8 with BOM so Excel opens it cleanly
- `out/checks.json` — UTF-8 JSON array
- `notes` explains missing fields or a page-level OCR error
- a row uses an empty string when a field could not be found

## Account-number handling

- The tool exports only the named fields above. It does not save raw OCR text.
- Free-text fields (`source`, `payee`, `memo`, `bank`) are scrubbed before
  export. Contiguous runs of 6+ digits, and groups of 3+ digits separated by
  spaces or hyphens, become `[redacted]`.
- The numeric amount, date, and check number are parsed separately, so they
  survive normal formatting such as `1,250.00` and `09/14/2026`.
- Source PDFs are **not modified**. This version produces CSV/JSON only; it
  does not create redacted copies of the checks.

No automated scrubber is perfect. An account number split by OCR into short
fragments, or one containing letters, may not be recognized. Review the exports
before sharing them, and never commit real checks to git.

## Bundled examples

The `examples/` folder contains:

- `demo_check_1.pdf` — Acme Office Supply, 124.50, check 1042
- `demo_check_2.pdf` — Jordan Ellis, 1,250.00, check 2210 (payee below label)
- `demo_check_3.pdf` — Northwind Traders, 89.99, check 3187 (payee on same row)
- `canadian_cheque_sample.pdf` — a public, low-resolution fictional sample

All synthetic names, amounts, account numbers, and routing numbers are
invented. The Canadian sample is CC BY-SA 3.0; see `examples/README.md` for
attribution. Its source image is low resolution, so OCR may report missing
fields for that one.

Regenerate the synthetic examples with:

```bash
python scripts/make_examples.py
```

## Tests

```bash
python -m pytest
```

The tests require Tesseract and run the full OCR/export pipeline against the
synthetic examples.

## Project layout

```text
checks/                 input PDFs (real checks are gitignored)
examples/               bundled demo checks and attribution
scripts/make_examples.py
src/check_reader/
  cli.py                command-line interface
  extract.py            field parsing and account-number scrubbing
  ocr.py                PDF rendering and Tesseract OCR
  processor.py          per-page processing and CSV/JSON exports
tests/
```
