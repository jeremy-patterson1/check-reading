from __future__ import annotations

from check_reader.extract import (
    Word,
    build_lines,
    extract_amount,
    extract_bank,
    extract_check_number,
    extract_date,
    extract_memo,
    extract_payee,
    scrub_account_numbers,
)


def make_lines(rows: list[tuple[str, int, int]]):
    words = []
    for index, (text, top, left) in enumerate(rows):
        words.append(
            Word(
                text=text,
                left=left,
                top=top,
                width=max(10, len(text) * 18),
                height=30,
                conf=95,
                block=1,
                par=1,
                line=index,
            )
        )
    return build_lines(words)


def test_date_formats():
    assert extract_date(make_lines([("DATE 09/14/2026", 100, 100)])) == "2026-09-14"
    assert extract_date(make_lines([("DATE 2026/10/15", 100, 100)])) == "2026-10-15"
    assert (
        extract_date(make_lines([("DATE October 2, 2026", 100, 100)]))
        == "2026-10-02"
    )
    assert (
        extract_date(make_lines([("DATE 2 October 2026", 100, 100)]))
        == "2026-10-02"
    )
    assert extract_date(make_lines([("not a date", 100, 100)])) == ""


def test_payee_same_line():
    lines = make_lines([("PAY TO THE ORDER OF Acme Office Supply", 300, 100)])
    assert extract_payee(lines) == "Acme Office Supply"


def test_payee_below_label():
    lines = make_lines(
        [
            ("PAY TO THE ORDER OF $ 1,250.00", 300, 100),
            ("Jordan Ellis", 380, 100),
        ]
    )
    assert extract_payee(lines) == "Jordan Ellis"


def test_payee_to_right_of_label():
    lines = make_lines(
        [
            ("$ 89.99", 314, 2195),
            ("Northwind Traders", 318, 564),
            ("PAY TO THE ORDER OF", 326, 113),
        ]
    )
    assert extract_payee(lines) == "Northwind Traders"


def test_amount_prefers_currency_and_handles_commas():
    lines = make_lines(
        [
            ("PAY TO THE ORDER OF Acme", 300, 100),
            ("$ 1,250.00", 300, 1900),
        ]
    )
    assert extract_amount(lines) == "1250.00"


def test_check_number_label_and_corner_fallback():
    label_lines = make_lines([("CHECK NO. 1042", 70, 2100)])
    assert extract_check_number(label_lines, [], 2550, 1050) == "1042"

    corner_words = [
        Word("3187", 2300, 70, 100, 30, 95, 1, 1, 1),
    ]
    assert extract_check_number([], corner_words, 2550, 1050) == "3187"


def test_memo_tolerates_ocr_label_variation():
    assert extract_memo(make_lines([("MEmMo October rent", 700, 100)])) == "October rent"
    assert (
        extract_memo(make_lines([("memo’. Office supplies", 700, 100)]))
        == "Office supplies"
    )


def test_bank_line():
    lines = make_lines([("HARBOR COMMUNITY BANK", 70, 100)])
    assert extract_bank(lines, 1050) == "HARBOR COMMUNITY BANK"


def test_account_numbers_are_scrubbed_but_other_numbers_survive():
    assert (
        scrub_account_numbers("Acme 0000123456789 2026-09-14 124.50 1042")
        == "Acme [redacted] 2026-09-14 124.50 1042"
    )
    assert scrub_account_numbers("routing 0999 999 999") == "routing [redacted]"
