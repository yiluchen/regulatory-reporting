"""抽取与幂等落库。"""
from pathlib import Path

import pytest

from dp.config import load_specs
from dp.extract import load_full, load_incremental, upsert

CONFIG = Path(__file__).resolve().parents[1] / "config" / "datasources.yaml"


@pytest.fixture
def spec():
    return {s.name: s for s in load_specs(CONFIG)}["loan_contract"]


def _row(contract: str, ts: str, balance: float = 100.0) -> dict:
    return {
        "contract_no": contract,
        "customer_no": "C00001",
        "org_code": "SH01",
        "product_type": "001",
        "loan_amount": 1000.0,
        "loan_balance": balance,
        "overdue_days": 0,
        "risk_class": "正常",
        "updated_at": ts,
    }


def test_full_load_keeps_latest_per_key(spec):
    rows = [_row("A", "2026-01-01 00:00:00", 100), _row("A", "2026-02-01 00:00:00", 200)]
    result = load_full(rows, spec)
    assert len(result) == 1
    assert result[0]["loan_balance"] == 200


def test_incremental_filters_by_watermark(spec):
    rows = [_row("A", "2026-01-01 00:00:00"), _row("B", "2026-03-01 00:00:00")]
    picked, watermark = load_incremental(rows, spec, "2026-01-15 00:00:00")
    assert [r["contract_no"] for r in picked] == ["B"]
    assert watermark == "2026-03-01 00:00:00"


def test_upsert_is_idempotent(spec):
    store = {}
    batch = [_row("A", "2026-01-01 00:00:00"), _row("B", "2026-01-01 00:00:00")]
    first = upsert(store, batch, spec)
    second = upsert(store, batch, spec)
    assert (first.inserted, first.updated, first.skipped) == (2, 0, 0)
    assert (second.inserted, second.updated, second.skipped) == (0, 0, 2)
    assert len(store) == 2


def test_upsert_only_overwrites_newer_watermark(spec):
    store = {}
    upsert(store, [_row("A", "2026-02-01 00:00:00", 100)], spec)
    stats = upsert(store, [_row("A", "2026-01-01 00:00:00", 999)], spec)
    assert stats.skipped == 1
    assert store[("A",)]["loan_balance"] == 100
    stats = upsert(store, [_row("A", "2026-03-01 00:00:00", 300)], spec)
    assert stats.updated == 1
    assert store[("A",)]["loan_balance"] == 300
