from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pymupdf
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output

from check_reader.extract import Word

if os.environ.get("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]


@dataclass(frozen=True)
class PageImage:
    page_number: int
    image: Image.Image
    width_pt: float
    height_pt: float


def tesseract_version() -> str:
    """Return the installed Tesseract version, raising if it is unavailable."""
    return str(pytesseract.get_tesseract_version())


def render_pdf(path: Path, dpi: int = 300) -> Iterator[PageImage]:
    """Render every PDF page to an RGB image."""
    document = pymupdf.open(path)
    try:
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(
                dpi=dpi, colorspace=pymupdf.csRGB, alpha=False
            )
            image = Image.frombytes(
                "RGB", (pixmap.width, pixmap.height), pixmap.samples
            )
            yield PageImage(
                page_number=index + 1,
                image=image,
                width_pt=page.rect.width,
                height_pt=page.rect.height,
            )
    finally:
        document.close()


def ocr_page(image: Image.Image, lang: str = "eng", psm: int = 3) -> list[Word]:
    """Run Tesseract on a page image and return words with pixel boxes."""
    prepared = ImageOps.autocontrast(image.convert("L"))
    scale = 1
    if prepared.width < 1200:
        scale = 2
        prepared = prepared.resize(
            (prepared.width * scale, prepared.height * scale), Image.LANCZOS
        )

    data = pytesseract.image_to_data(
        prepared,
        lang=lang,
        config=f"--psm {psm}",
        output_type=Output.DICT,
    )

    words: list[Word] = []
    for index, text in enumerate(data["text"]):
        text = text.strip()
        if not text:
            continue
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError):
            confidence = -1.0
        words.append(
            Word(
                text=text,
                left=int(data["left"][index] / scale),
                top=int(data["top"][index] / scale),
                width=int(data["width"][index] / scale),
                height=int(data["height"][index] / scale),
                conf=confidence,
                block=int(data["block_num"][index]),
                par=int(data["par_num"][index]),
                line=int(data["line_num"][index]),
            )
        )
    return words
