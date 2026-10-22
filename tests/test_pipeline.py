from __future__ import annotations

import json
from pathlib import Path

from check_reader.cli import main
from check_reader.processor import CheckProcessor, write_exports

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

EXPECTED = {
    "demo_check_1.pdf": {
        "date": "2026-09-14",
        "payee": "Acme Office Supply",
        "amount": "124.50",
        "check_number": "1042",
        "memo": "Invoice 1042",
        "bank": "FIRST NATIONAL DEMO BANK",
    },
    "demo_check_2.pdf": {
        "date": "2026-10-02",
        "payee": "Jordan Ellis",
        "amount": "1250.00",
        "check_number": "2210",
        "memo": "October rent",
        "bank": "RIVERBEND CREDIT UNION",
    },
    "demo_check_3.pdf": {
        "date": "2026-10-15",
        "payee": "Northwind Traders",
        "amount": "89.99",
        "check_number": "3187",
        "memo": "Office supplies",
        "bank": "HARBOR COMMUNITY BANK",
    },
}


def test_synthetic_examples_extract_expected_fields():
    processor = CheckProcessor()
    for filename, expected in EXPECTED.items():
        records = processor.process_pdf(EXAMPLES / filename)
        assert len(records) == 1
        record = records[0]
        for field, value in expected.items():
            assert record[field] == value, (filename, field, record)
        assert record["notes"] == ""


def test_exports_contain_names_and_values_but_not_account_numbers(tmp_path: Path):
    processor = CheckProcessor()
    records = processor.process_pdf(EXAMPLES / "demo_check_2.pdf")
    csv_path, json_path = write_exports(records, tmp_path)

    csv_text = csv_path.read_text(encoding="utf-8-sig")
    json_text = json_path.read_text(encoding="utf-8")

    for secret in ("088888888", "0000987654321"):
        assert secret not in csv_text
        assert secret not in json_text

    assert "Jordan Ellis" in csv_text
    assert "1250.00" in csv_text
    assert json.loads(json_text)[0]["payee"] == "Jordan Ellis"


def test_cli_prints_extracted_values(tmp_path: Path, capsys):
    code = main(
        ["--input", str(EXAMPLES / "demo_check_1.pdf"), "-o", str(tmp_path)]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "payee='Acme Office Supply'" in output
    assert "amount='124.50'" in output
    assert (tmp_path / "checks.csv").exists()
    assert (tmp_path / "checks.json").exists()
