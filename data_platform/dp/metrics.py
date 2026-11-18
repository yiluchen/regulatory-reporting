"""DM 集市：信贷主题宽表指标。"""
from __future__ import annotations

from collections import defaultdict

NPL_CLASSES = {"次级", "可疑", "损失"}


def build_credit_wide(
    loans: list[dict], provisions: list[dict], stat_date: str
) -> list[dict]:
    """按机构汇总信贷指标，供 EAST / 1104 / 人行报送统一取数。"""
    balance: dict[str, float] = defaultdict(float)
    npl: dict[str, float] = defaultdict(float)
    overdue: dict[str, float] = defaultdict(float)
    count: dict[str, int] = defaultdict(int)

    for row in loans:
        org = str(row["org_code"])
        amount = float(row["loan_balance"])
        balance[org] += amount
        count[org] += 1
        if row["risk_class"] in NPL_CLASSES:
            npl[org] += amount
        if int(row["overdue_days"]) > 0:
            overdue[org] += amount

    provision: dict[str, float] = defaultdict(float)
    for row in provisions:
        provision[str(row["org_code"])] += float(row["provision_amount"])

    result: list[dict] = []
    for org in sorted(balance):
        total = balance[org]
        npl_amount = npl[org]
        result.append(
            {
                "stat_date": stat_date,
                "org_code": org,
                "loan_count": count[org],
                "loan_balance": round(total, 2),
                "npl_balance": round(npl_amount, 2),
                "npl_ratio": round(npl_amount / total, 6) if total else 0.0,
                "overdue_balance": round(overdue[org], 2),
                "overdue_ratio": round(overdue[org] / total, 6) if total else 0.0,
                "provision_amount": round(provision[org], 2),
                "provision_coverage": round(provision[org] / npl_amount, 6) if npl_amount else 0.0,
            }
        )
    return result
