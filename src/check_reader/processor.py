from __future__ import annotations

import csv
import json
from pathlib import Path

from check_reader.extract import build_lines, extract_fields, scrub_account_numbers
from check_reader.ocr import ocr_page, render_pdf

FIELDNAMES = [
    "source",
    "page",
    "date",
    "payee",
    "amount",
    "check_number",
    "memo",
    "bank",
    "notes",
]

def _source_label(path: Path) -> str:
    return scrub_account_numbers(str(path))


class CheckProcessor:
    def __init__(self, dpi: int = 300, lang: str = "eng", psm: int = 3):
        self.dpi = dpi
        self.lang = lang
        self.psm = psm

    def process_pdf(self, pdf_path: Path) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for page in render_pdf(pdf_path, dpi=self.dpi):
            notes: list[str] = []
            try:
                words = ocr_page(page.image, lang=self.lang, psm=self.psm)
            except Exception as exc:  # keep other pages usable if one page fails
                words = []
                notes.append(f"OCR failed: {type(exc).__name__}")

            if not words and not notes:
                notes.append("no text found")

            lines = build_lines(words)
            fields = extract_fields(
                lines, words, page.image.width, page.image.height
            )
            notes.extend(fields.notes)

            records.append(
                {
                    "source": _source_label(pdf_path),
                    "page": page.page_number,
                    "date": fields.date,
                    "payee": scrub_account_numbers(fields.payee),
                    "amount": fields.amount,
                    "check_number": fields.check_number,
                    "memo": scrub_account_numbers(fields.memo),
                    "bank": scrub_account_numbers(fields.bank),
                    "notes": "; ".join(notes),
                }
            )

        if not records:
            raise ValueError("PDF has no pages")
        return records


def write_exports(
    records: list[dict[str, object]], output_dir: Path
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "checks.csv"
    json_path = output_dir / "checks.json"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)

    json_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return csv_path, json_path
