"""校验与通过率。"""
from pathlib import Path

import pytest

from dp.config import load_specs
from dp.validate import Report, validate_cross_table, validate_table

CONFIG = Path(__file__).resolve().parents[1] / "config" / "datasources.yaml"


@pytest.fixture
def spec():
    return {s.name: s for s in load_specs(CONFIG)}["loan_contract"]


def _row(**overrides) -> dict:
    row = {
        "contract_no": "A",
        "customer_no": "C00001",
        "org_code": "SH01",
        "product_type": "001",
        "loan_amount": 1000.0,
        "loan_balance": 800.0,
        "overdue_days": 0,
        "risk_class": "正常",
        "updated_at": "2026-01-01 00:00:00",
    }
    row.update(overrides)
    return row


def test_clean_rows_pass_all_checks(spec):
    report = validate_table([_row(), _row(contract_no="B")], spec)
    assert report.pass_rate == 1.0
    assert report.issues == []


def test_bad_rows_lower_pass_rate(spec):
    report = validate_table([_row(), _row(contract_no="B", risk_class="未知")], spec)
    assert report.pass_rate < 1.0
    assert any(i.rule == "enum:risk_class" for i in report.issues)


def test_duplicate_key_is_reported(spec):
    report = validate_table([_row(), _row(loan_balance=900)], spec)
    assert any(i.rule == "unique_business_key" for i in report.issues)


def test_cross_table_tolerance():
    report = Report()
    validate_cross_table([{"v": 100.0}], "v", [{"v": 100.0}], "v", 0.0, "勾稽", report)
    assert report.pass_rate == 1.0

    report = Report()
    validate_cross_table([{"v": 100.0}], "v", [{"v": 90.0}], "v", 0.0, "勾稽", report)
    assert report.pass_rate == 0.0
    assert report.issues[0].level == "cross"
