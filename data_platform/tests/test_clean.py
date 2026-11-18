"""清洗规则。"""
from pathlib import Path

import pytest

from dp.clean import clean
from dp.config import load_specs

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


def test_strips_and_normalizes(spec):
    rows, stats = clean([_row(customer_no="  C00001  ", org_code=" SH01 ")], spec)
    assert rows[0]["customer_no"] == "C00001"
    assert rows[0]["org_code"] == "SH01"
    assert stats.dropped == 0


def test_drops_rows_with_null_business_key(spec):
    rows, stats = clean([_row(contract_no=None), _row(contract_no="B")], spec)
    assert [r["contract_no"] for r in rows] == ["B"]
    assert stats.dropped == 1


def test_drops_invalid_enum_and_range(spec):
    _, stats = clean([_row(risk_class="未知"), _row(loan_balance=-1), _row(overdue_days=99999)], spec)
    assert stats.invalid_value == 3
    assert stats.output_rows == 0


def test_dedup_keeps_latest(spec):
    rows, stats = clean(
        [_row(loan_balance=100, updated_at="2026-01-01 00:00:00"),
         _row(loan_balance=200, updated_at="2026-02-01 00:00:00")],
        spec,
    )
    assert len(rows) == 1
    assert rows[0]["loan_balance"] == 200
    assert stats.duplicated == 1
