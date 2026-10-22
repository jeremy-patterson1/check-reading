from __future__ import annotations

import argparse
import sys
from pathlib import Path

from check_reader.ocr import tesseract_version
from check_reader.processor import CheckProcessor, write_exports


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check-reader",
        description=(
            "OCR PDF checks and export payee, amount, date, check number, "
            "memo, and bank. Account/routing digit runs are not exported."
        ),
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="PDF file or folder of PDFs (default: checks)",
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input_option",
        default=None,
        metavar="INPUT",
        help="PDF file or folder of PDFs (default: checks)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="out",
        help="folder for checks.csv and checks.json (default: out)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="render resolution used for OCR (default: 300)",
    )
    parser.add_argument(
        "--lang",
        default="eng",
        help="Tesseract language code (default: eng)",
    )
    return parser


def _missing_tesseract_message() -> str:
    return (
        "Tesseract OCR was not found.\n"
        "Linux: install tesseract-ocr (for example: sudo apt install tesseract-ocr).\n"
        "Windows: install Tesseract and add it to PATH, or set TESSERACT_CMD "
        "to the full path of tesseract.exe.\n"
        "See https://github.com/UB-Mannheim/tesseract/wiki"
    )


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not 150 <= args.dpi <= 600:
        print("error: --dpi must be between 150 and 600", file=sys.stderr)
        return 2

    try:
        version = tesseract_version()
    except Exception:
        print(_missing_tesseract_message(), file=sys.stderr)
        return 2

    input_value = args.input_option or args.input or "checks"
    input_path = Path(input_value).expanduser()
    if input_path.is_dir():
        pdfs = sorted(
            path for path in input_path.rglob("*.pdf") if path.is_file()
        )
        output_path = Path(args.output).expanduser().resolve()
        pdfs = [
            path
            for path in pdfs
            if output_path not in path.resolve().parents
        ]
    elif input_path.is_file() and input_path.suffix.lower() == ".pdf":
        pdfs = [input_path]
    else:
        print(f"error: no PDF found at {input_path}", file=sys.stderr)
        return 2

    if not pdfs:
        print(f"error: no PDFs found in {input_path}", file=sys.stderr)
        if input_path.is_dir() and input_path.name == "checks":
            print(
                "Add PDFs to checks/ or try: python -m check_reader --input examples",
                file=sys.stderr,
            )
        return 2

    processor = CheckProcessor(dpi=args.dpi, lang=args.lang)
    records: list[dict[str, object]] = []
    failures = 0

    for index, pdf in enumerate(pdfs, start=1):
        print(f"[{index}/{len(pdfs)}] Reading {pdf}")
        try:
            pdf_records = processor.process_pdf(pdf)
            records.extend(pdf_records)
            for record in pdf_records:
                print(
                    "  page {page}: date={date!r} payee={payee!r} "
                    "amount={amount!r} check_number={check_number!r} "
                    "memo={memo!r} bank={bank!r}".format(**record)
                )
                if record["notes"]:
                    print(f"    notes: {record['notes']}")
        except Exception as exc:
            failures += 1
            print(f"error: {pdf}: {type(exc).__name__}: {exc}", file=sys.stderr)

    if not records:
        print("error: no records were produced", file=sys.stderr)
        return 1

    csv_path, json_path = write_exports(records, Path(args.output))
    print(f"Wrote {len(records)} check(s) to {csv_path} and {json_path}")
    print(f"Used Tesseract {version}")
    if failures:
        print(f"Finished with {failures} failed PDF(s)", file=sys.stderr)
        return 1
    return 0
