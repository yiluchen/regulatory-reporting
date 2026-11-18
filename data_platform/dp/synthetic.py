"""合成数据：用于离线演示，不含任何真实客户或账户信息。"""
from __future__ import annotations

import random
from datetime import date, timedelta

ORGS = ["SH01", "SH02", "SZ01"]
PRODUCTS = ["001", "002", "003"]
RISK = ["正常", "关注", "次级", "可疑", "损失"]


def _ts(day: int) -> str:
    return (date(2026, 1, 1) + timedelta(days=day)).strftime("%Y-%m-%d 08:00:00")


def generate_loans(n: int = 300, dirty_ratio: float = 0.3, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    for i in range(n):
        amount = round(rng.uniform(1_000_000, 20_000_000), 2)
        row = {
            "contract_no": f"LN2026{i:05d}",
            "customer_no": f"C{rng.randint(1, 120):05d}",
            "org_code": rng.choice(ORGS),
            "product_type": rng.choice(PRODUCTS),
            "loan_amount": amount,
            "loan_balance": round(amount * rng.uniform(0.2, 1.0), 2),
            "overdue_days": 0 if rng.random() < 0.88 else rng.randint(1, 400),
            "risk_class": rng.choices(RISK, weights=[70, 15, 8, 5, 2])[0],
            "updated_at": _ts(rng.randint(0, 60)),
        }
        rows.append(row)

    rng_dirty = random.Random(seed + 1)
    for _ in range(int(n * dirty_ratio)):
        row = dict(rng_dirty.choice(rows))
        kind = rng_dirty.choice(["null_customer", "bad_enum", "negative", "out_of_range", "duplicate"])
        row["updated_at"] = _ts(rng.randint(0, 60))
        if kind == "null_customer":
            row["customer_no"] = None
        elif kind == "bad_enum":
            row["risk_class"] = "未知"
        elif kind == "negative":
            row["loan_balance"] = -abs(row["loan_balance"])
        elif kind == "out_of_range":
            row["overdue_days"] = 99999
        rows.append(row)   # duplicate 场景：同主键不同水位
    return rows


def generate_repayments(loans: list[dict], seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    rows: list[dict] = []
    for loan in loans:
        contract = loan.get("contract_no")
        if not contract:
            continue
        for period in (1, 2):
            due = round(float(loan["loan_amount"]) / 24, 2)
            rows.append(
                {
                    "contract_no": contract,
                    "period_no": period,
                    "principal_due": due,
                    "principal_paid": round(due * rng.uniform(0.5, 1.0), 2),
                    "interest_due": round(due * 0.045, 2),
                    "interest_paid": round(due * 0.045 * rng.uniform(0.5, 1.0), 2),
                    "updated_at": loan["updated_at"],
                }
            )
    return rows


def generate_provisions(loans: list[dict]) -> list[dict]:
    from .metrics import NPL_CLASSES

    stats: dict[str, list[float]] = {}
    for loan in loans:
        org = loan.get("org_code")
        if not org:
            continue
        bucket = stats.setdefault(org, [0.0, 0.0])
        bucket[0] += float(loan.get("loan_balance") or 0)
        if loan.get("risk_class") in NPL_CLASSES:
            bucket[1] += float(loan.get("loan_balance") or 0)

    rows = []
    for org, (_, npl) in stats.items():
        rows.append(
            {
                "org_code": org,
                "stat_date": "2026-03-01",
                "provision_amount": round(npl * 1.6 + 1_000_000, 2),
                "updated_at": _ts(60),
            }
        )
    return rows
