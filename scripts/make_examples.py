"""Create clearly fictional example check PDFs for local testing.

All names, amounts, account numbers, and routing numbers below are invented.
Run from the repository root:

    python scripts/make_examples.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/consolab.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    candidates = list(FONT_CANDIDATES)
    if mono:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "C:/Windows/Fonts/consola.ttf",
            "/System/Library/Fonts/Supplemental/Courier New.ttf",
        ]
    elif bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    raise RuntimeError(
        "No usable TrueType font found. Install DejaVu Sans or update "
        "scripts/make_examples.py with a font path for this system."
    )


def _draw_check(
    bank: str,
    bank_address: str,
    payee: str,
    amount: str,
    amount_words: str,
    date_text: str,
    check_number: str,
    memo: str,
    routing: str,
    account: str,
    payee_on_next_line: bool = False,
) -> Image.Image:
    image = Image.new("RGB", (2550, 1050), "white")
    draw = ImageDraw.Draw(image)

    draw.text((110, 70), bank, font=_font(46, bold=True), fill="black")
    draw.text((110, 135), bank_address, font=_font(26), fill="black")

    draw.text(
        (2420, 70),
        f"CHECK NO. {check_number}",
        font=_font(34, bold=True),
        fill="black",
        anchor="ra",
    )
    draw.text(
        (2420, 175),
        f"DATE {date_text}",
        font=_font(34),
        fill="black",
        anchor="ra",
    )

    label_font = _font(30)
    payee_font = _font(46)
    draw.text((110, 320), "PAY TO THE ORDER OF", font=label_font, fill="black")
    if payee_on_next_line:
        draw.text((110, 380), payee, font=payee_font, fill="black")
    else:
        draw.text((560, 310), payee, font=payee_font, fill="black")

    draw.rectangle((1980, 285, 2440, 405), outline="black", width=3)
    draw.text(
        (2410, 305),
        f"$ {amount}",
        font=_font(52, bold=True),
        fill="black",
        anchor="ra",
    )

    draw.text((110, 475), amount_words, font=_font(32), fill="black")

    draw.text((110, 700), "MEMO", font=_font(28), fill="black")
    draw.text((230, 690), memo, font=_font(34), fill="black")

    draw.line((1500, 820, 2380, 820), fill="black", width=2)
    draw.text((1530, 735), "Authorized signature", font=_font(24), fill="black")

    # The MICR line is fake. The tool never exports it; this is here so the
    # example PDF looks and behaves like a real scanned check.
    micr = f"|: {routing} |: {account} || {check_number} |"
    draw.text((110, 930), micr, font=_font(44, mono=True), fill="black")

    return image


def _save_as_pdf(image: Image.Image, path: Path) -> None:
    width_in = 8.5
    height_in = width_in * image.height / image.width
    document = pymupdf.open()
    try:
        page = document.new_page(width=width_in * 72, height=height_in * 72)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        page.insert_image(page.rect, stream=buffer.getvalue())
        document.save(path, garbage=3, deflate=True)
    finally:
        document.close()


def main() -> None:
    EXAMPLES.mkdir(parents=True, exist_ok=True)

    checks = [
        {
            "filename": "demo_check_1.pdf",
            "bank": "FIRST NATIONAL DEMO BANK",
            "bank_address": "100 Example Avenue, Demo City, ST 00000",
            "payee": "Acme Office Supply",
            "amount": "124.50",
            "amount_words": "One Hundred Twenty-Four and 50/100 DOLLARS",
            "date_text": "09/14/2026",
            "check_number": "1042",
            "memo": "Invoice 1042",
            "routing": "099999999",
            "account": "0000123456789",
            "payee_on_next_line": False,
        },
        {
            "filename": "demo_check_2.pdf",
            "bank": "RIVERBEND CREDIT UNION",
            "bank_address": "200 Sample Road, Fictionaltown, ST 00000",
            "payee": "Jordan Ellis",
            "amount": "1,250.00",
            "amount_words": "One Thousand Two Hundred Fifty and 00/100 DOLLARS",
            "date_text": "October 2, 2026",
            "check_number": "2210",
            "memo": "October rent",
            "routing": "088888888",
            "account": "0000987654321",
            "payee_on_next_line": True,
        },
        {
            "filename": "demo_check_3.pdf",
            "bank": "HARBOR COMMUNITY BANK",
            "bank_address": "300 Placeholder Street, Testville, ST 00000",
            "payee": "Northwind Traders",
            "amount": "89.99",
            "amount_words": "Eighty-Nine and 99/100 DOLLARS",
            "date_text": "10/15/2026",
            "check_number": "3187",
            "memo": "Office supplies",
            "routing": "077777777",
            "account": "0000555566666",
            "payee_on_next_line": False,
        },
    ]

    for values in checks:
        filename = values.pop("filename")
        image = _draw_check(**values)
        _save_as_pdf(image, EXAMPLES / filename)
        print(f"wrote {EXAMPLES / filename}")

    public_sample = EXAMPLES / "canadian_cheque_sample.png"
    if public_sample.exists():
        image = Image.open(public_sample).convert("RGB")
        _save_as_pdf(image, EXAMPLES / "canadian_cheque_sample.pdf")
        print(f"wrote {EXAMPLES / 'canadian_cheque_sample.pdf'}")


if __name__ == "__main__":
    main()
