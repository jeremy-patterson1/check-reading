from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

_AMOUNT_RE = re.compile(
    r"(?<![\d,])(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})(?!\d)"
)
_CHECK_RE = re.compile(
    r"\b(?:CHECK|CHK)\s*(?:NO\.?|NUMBER|#)?\s*[:\-]?\s*(\d{1,6})\b",
    re.IGNORECASE,
)
_MEMO_RE = re.compile(r"\bM\s*E\s*M+\s*O\b\s*[:\-]?\s*(.*)", re.IGNORECASE)
_PAYEE_RES = (
    re.compile(
        r"\bPAY\s+TO\s+(?:THE\s+)?ORDER\s+OF\b\s*[:\-]?\s*(.*)", re.IGNORECASE
    ),
    re.compile(r"\bORDER\s+OF\b\s*[:\-]?\s*(.*)", re.IGNORECASE),
    re.compile(r"\bPAY\s+TO\b\s*[:\-]?\s*(.*)", re.IGNORECASE),
)
_BANK_RE = re.compile(
    r"\b(?:BANK|CREDIT\s+UNION|TRUST|SAVINGS)\b", re.IGNORECASE
)
_DATE_NUMERIC_RE = re.compile(
    r"(?<!\d)(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})(?!\d)"
)
_DATE_COMPACT_RE = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")
_DATE_DAY_MONTH_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\b\.?,?\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONTH_RE = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# Contiguous digit runs, or groups of 3+ digits separated by spaces/hyphens,
# are treated as account/routing numbers. Date-like 4-2-2 groups do not match.
_ACCOUNT_DIGITS_RE = re.compile(
    r"(?<!\d)(?:\d{6,}|\d{3,6}(?:[ \t\-]\d{3,6}){1,3})(?!\d)"
)


@dataclass(frozen=True)
class Word:
    text: str
    left: int
    top: int
    width: int
    height: int
    conf: float = 0.0
    block: int = 0
    par: int = 0
    line: int = 0

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass(frozen=True)
class Line:
    text: str
    left: int
    top: int
    right: int
    bottom: int
    words: tuple[Word, ...] = ()


@dataclass(frozen=True)
class ExtractedFields:
    date: str = ""
    payee: str = ""
    amount: str = ""
    check_number: str = ""
    memo: str = ""
    bank: str = ""
    notes: tuple[str, ...] = ()


def build_lines(words: list[Word]) -> list[Line]:
    """Group Tesseract words into lines sorted in reading order."""
    groups: dict[tuple[int, int, int], list[Word]] = defaultdict(list)
    for word in words:
        if word.text.strip():
            groups[(word.block, word.par, word.line)].append(word)

    lines: list[Line] = []
    for group in groups.values():
        group.sort(key=lambda word: word.left)
        text = re.sub(r"\s+", " ", " ".join(w.text.strip() for w in group)).strip()
        if not text:
            continue
        lines.append(
            Line(
                text=text,
                left=min(word.left for word in group),
                top=min(word.top for word in group),
                right=max(word.right for word in group),
                bottom=max(word.bottom for word in group),
                words=tuple(group),
            )
        )

    lines.sort(key=lambda line: (line.top, line.left))
    return lines


def scrub_account_numbers(text: str) -> str:
    """Replace long digit runs so account numbers cannot reach an export."""
    if not text:
        return ""
    return _ACCOUNT_DIGITS_RE.sub("[redacted]", text).strip()


def _clean_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = value.strip(" :;,.|_-’'\"“”‘`")
    return value.strip()


def _clean_payee(value: str) -> str:
    value = _clean_text(value)
    upper = value.upper()
    if not value or upper in {"ORDER OF", "PAY TO", "PAY TO THE ORDER OF"}:
        return ""
    if "$" in value:
        value = value.split("$", 1)[0]
    value = re.sub(r"\s+\$?\d{1,3}(?:,\d{3})*\.\d{2}\s*$", "", value)
    value = _clean_text(value)
    return value


def _looks_like_payee(value: str) -> str:
    value = _clean_payee(value)
    if not value:
        return ""
    upper = value.upper()
    if any(
        marker in upper
        for marker in (
            "ORDER OF",
            "PAY TO",
            "DOLLARS",
            "MEMO",
            "DATE",
            "CHECK NO",
            "SIGNATURE",
            "AUTHORIZED",
        )
    ):
        return ""
    if _AMOUNT_RE.search(value):
        return ""
    if re.fullmatch(r"[\d\s.,$#:;|_\-]+", value):
        return ""
    return value


def _safe_date(year: int, month: int, day: int) -> str | None:
    if year < 100:
        year += 2000 if year <= 69 else 1900
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _parse_numeric_date(first: str, second: str, third: str) -> str | None:
    if len(first) == 4:
        year, month, day = int(first), int(second), int(third)
    else:
        year = int(third)
        if int(first) > 12 and int(second) <= 12:
            day, month = int(first), int(second)
        else:
            month, day = int(first), int(second)
    return _safe_date(year, month, day)


def extract_date(lines: list[Line]) -> str:
    """Return the first plausible check date as an ISO date string."""
    candidates: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        has_date_label = "DATE" in line.text.upper()
        for match in _DATE_NUMERIC_RE.finditer(line.text):
            parsed = _parse_numeric_date(*match.groups())
            if parsed:
                candidates.append((0 if has_date_label else 1, index, parsed))
        if has_date_label:
            for match in _DATE_COMPACT_RE.finditer(line.text):
                parsed = _safe_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                if parsed:
                    candidates.append((0, index, parsed))
        for match in _MONTH_RE.finditer(line.text):
            month = _MONTHS[match.group(1)[:3].lower()]
            after = line.text[match.end() :]
            day_match = re.match(r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", after)
            if day_match:
                parsed = _safe_date(
                    int(day_match.group(2)), month, int(day_match.group(1))
                )
                if parsed:
                    candidates.append((0 if has_date_label else 1, index, parsed))
        for match in _DATE_DAY_MONTH_RE.finditer(line.text):
            month = _MONTHS[match.group(2)[:3].lower()]
            parsed = _safe_date(
                int(match.group(3)), month, int(match.group(1))
            )
            if parsed:
                candidates.append((0 if has_date_label else 1, index, parsed))

    if not candidates:
        return ""
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def extract_payee(lines: list[Line]) -> str:
    """Find the payee following a PAY TO THE ORDER OF label."""
    for line in lines:
        match = None
        for pattern in _PAYEE_RES:
            match = pattern.search(line.text)
            if match:
                break
        if not match:
            continue

        payee = _looks_like_payee(match.group(1))
        if payee:
            return payee

        # OCR often splits a same-row payee into its own line. Prefer the
        # nearest payee-shaped line to the right of the label.
        label_center = (line.top + line.bottom) / 2
        right_candidates = []
        for other in lines:
            if other is line or other.left <= line.left:
                continue
            other_center = (other.top + other.bottom) / 2
            if abs(other_center - label_center) > max(40, line.bottom - line.top):
                continue
            candidate = _looks_like_payee(other.text)
            if candidate:
                right_candidates.append((other.left, candidate))
        if right_candidates:
            return min(right_candidates, key=lambda item: item[0])[1]

        # Or the payee can be printed directly below the label.
        below_candidates = []
        max_distance = max(120, 2 * (line.bottom - line.top))
        for other in lines:
            if other.top <= line.top or other.top - line.bottom > max_distance:
                continue
            candidate = _looks_like_payee(other.text)
            if candidate:
                below_candidates.append((other.top, candidate))
        if below_candidates:
            return min(below_candidates, key=lambda item: item[0])[1]
    return ""


def extract_amount(lines: list[Line]) -> str:
    """Return the numeric check amount, preferring a currency-prefixed value."""
    plain: str | None = None
    for line in lines:
        for match in _AMOUNT_RE.finditer(line.text):
            whole = match.group(1).lstrip(",")
            try:
                amount = Decimal(f"{whole.replace(',', '')}.{match.group(2)}")
            except InvalidOperation:
                continue
            if amount <= 0:
                continue
            formatted = f"{amount:.2f}"
            if "$" in line.text[max(0, match.start() - 4) : match.start()]:
                return formatted
            if plain is None:
                plain = formatted
    return plain or ""


def extract_check_number(
    lines: list[Line], words: list[Word], width: int, height: int
) -> str:
    """Read a labelled check number, then fall back to the top-right corner."""
    for line in lines:
        match = _CHECK_RE.search(line.text)
        if match:
            return match.group(1)

    right_words = [
        word
        for word in words
        if word.left > width * 0.65
        and word.top < height * 0.30
        and re.fullmatch(r"\d{1,6}", word.text.strip())
    ]
    if right_words:
        return max(right_words, key=lambda word: word.left).text.strip()

    bottom_words = [
        word
        for word in words
        if word.left > width * 0.70
        and word.top > height * 0.70
        and re.fullmatch(r"\d{3,6}", word.text.strip())
    ]
    if bottom_words:
        return max(bottom_words, key=lambda word: word.left).text.strip()
    return ""


def extract_memo(lines: list[Line]) -> str:
    """Read the memo line, using the following line when the label is alone."""
    for index, line in enumerate(lines):
        match = _MEMO_RE.search(line.text)
        if not match:
            continue
        memo = _clean_text(match.group(1))
        if memo:
            return memo
        for next_line in lines[index + 1 : index + 2]:
            memo = _clean_text(next_line.text)
            if memo and not re.fullmatch(r"[\d\s\-]+", memo):
                return memo
    return ""


def extract_bank(lines: list[Line], height: int) -> str:
    """Use a bank-like line from the top third of the check, when present."""
    for line in lines:
        if line.top > height * 0.35:
            break
        if _BANK_RE.search(line.text):
            value = re.split(r"\bDATE\b|\bCHECK\s+NO\b", line.text, maxsplit=1, flags=re.IGNORECASE)[0]
            return _clean_text(value)
    return ""


def extract_fields(
    lines: list[Line], words: list[Word], width: int, height: int
) -> ExtractedFields:
    """Extract all supported fields and remove account-like numbers from text."""
    check_date = extract_date(lines)
    payee = scrub_account_numbers(extract_payee(lines))
    amount = extract_amount(lines)
    check_number = extract_check_number(lines, words, width, height)
    memo = scrub_account_numbers(extract_memo(lines))
    bank = scrub_account_numbers(extract_bank(lines, height))

    notes: list[str] = []
    if not check_date:
        notes.append("date not found")
    if not payee:
        notes.append("payee not found")
    if not amount:
        notes.append("amount not found")
    if not check_number:
        notes.append("check number not found")

    return ExtractedFields(
        date=check_date,
        payee=payee,
        amount=amount,
        check_number=check_number,
        memo=memo,
        bank=bank,
        notes=tuple(notes),
    )
