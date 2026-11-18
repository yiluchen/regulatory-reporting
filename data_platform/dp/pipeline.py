"""端到端演示：抽取 → 清洗 → 校验 → 指标 → 调度。"""
from __future__ import annotations

import argparse
from pathlib import Path

from .clean import clean
from .config import load_specs
from .extract import Store, load_full, to_rows, upsert
from .metrics import build_credit_wide
from .scheduler import Scheduler, Task
from .synthetic import generate_loans, generate_provisions, generate_repayments
from .validate import (
    Report,
    validate_cross_table,
    validate_repayment_balance,
    validate_table,
)

CONFIG = Path(__file__).resolve().parent.parent / "config" / "datasources.yaml"


def run(dirty_ratio: float = 0.3, seed: int = 42) -> dict:
    specs = {s.name: s for s in load_specs(CONFIG)}
    loan_spec, repay_spec = specs["loan_contract"], specs["repayment"]

    raw_loans = generate_loans(dirty_ratio=dirty_ratio, seed=seed)

    # 1. 入湖前首轮校验：脏数据、重复主键都会在这里暴露
    raw_report = validate_table(raw_loans, loan_spec)

    # 2. ODS 全量初始化（同主键保留最新水位）
    ods_store: Store = {}
    ods_stats = upsert(ods_store, load_full(raw_loans, loan_spec), loan_spec)

    # 3. DWD 清洗
    dwd_loans, clean_stats = clean(raw_loans, loan_spec)
    dwd_report = validate_table(dwd_loans, loan_spec)

    # 4. 还款明细：清洗 + 表内平衡校验
    raw_repay = generate_repayments(dwd_loans, seed=seed)
    repay_rows, repay_stats = clean(raw_repay, repay_spec)
    validate_repayment_balance(repay_rows, dwd_report)

    # 5. DM 指标 + 表间勾稽
    provisions = generate_provisions(dwd_loans)
    dm_rows = build_credit_wide(dwd_loans, provisions, stat_date="2026-03-01")
    validate_cross_table(
        dwd_loans, "loan_balance", dm_rows, "loan_balance", 0.0, "贷款余额勾稽", dwd_report
    )

    # 6. 增量重放：同一批数据写两次，第二次必须零变更
    replay_store: Store = {}
    batch = load_full(raw_loans, loan_spec)
    first = upsert(replay_store, batch, loan_spec)
    second = upsert(replay_store, batch, loan_spec)

    return {
        "raw_pass_rate": raw_report.pass_rate,
        "dwd_pass_rate": dwd_report.pass_rate,
        "clean": clean_stats,
        "repay": repay_stats,
        "dm": dm_rows,
        "replay": (first, second),
        "ods_rows": len(to_rows(ods_store)),
        "reports": (raw_report, dwd_report),
    }


def _print(result: dict) -> None:
    raw, dwd = result["reports"]
    print("=" * 68)
    print("ODS 入湖首轮校验（原始数据）")
    print(raw.summary())
    print("-" * 68)
    print("DWD 清洗后校验")
    print(dwd.summary())
    print(
        f"清洗：输入 {result['clean'].input_rows} 行 → 输出 {result['clean'].output_rows} 行，"
        f"去重 {result['clean'].duplicated}，非法 {result['clean'].invalid_value}"
    )
    print("-" * 68)
    print("DM 信贷主题宽表")
    header = f"{'机构':<6}{'笔数':>6}{'贷款余额':>16}{'不良率':>10}{'逾期率':>10}{'拨备覆盖率':>12}"
    print(header)
    for row in result["dm"]:
        print(
            f"{row['org_code']:<6}{row['loan_count']:>6}{row['loan_balance']:>16,.0f}"
            f"{row['npl_ratio']:>10.2%}{row['overdue_ratio']:>10.2%}{row['provision_coverage']:>12.2%}"
        )
    print("-" * 68)
    first, second = result["replay"]
    print(
        f"增量重放：首次 新增 {first.inserted} 更新 {first.updated} 跳过 {first.skipped}；"
        f"重放 新增 {second.inserted} 更新 {second.updated} 跳过 {second.skipped}（应为 0/0）"
    )
    print("=" * 68)


def build_scheduler(result: dict) -> Scheduler:
    """把一次批处理拆成 DAG，演示重试与下游跳过。"""
    def step(name: str):
        def _run():
            print(f"  [scheduler] 执行 {name}")
            return name

        return _run

    sched = Scheduler(alert=lambda name, err: print(f"  [alert] {name} 失败: {err}"))
    sched.add(Task("ods_load", step("ods_load")))
    sched.add(Task("dwd_clean", step("dwd_clean"), depends_on=["ods_load"]))
    sched.add(Task("validate", step("validate"), depends_on=["dwd_clean"]))
    sched.add(Task("dm_build", step("dm_build"), depends_on=["dwd_clean"]))
    return sched


def main() -> None:
    parser = argparse.ArgumentParser(description="监管报送数据中台演示")
    parser.add_argument("--demo", action="store_true", help="使用合成数据跑通全链路")
    parser.add_argument("--dirty-rows", type=float, default=0.3, help="脏数据比例 (0-1)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = run(dirty_ratio=args.dirty_rows, seed=args.seed)
    _print(result)
    print("\n调度 DAG：")
    for name, res in build_scheduler(result).run().items():
        print(f"  {name:<12} {res.status}")


if __name__ == "__main__":
    main()
