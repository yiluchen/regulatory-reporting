# 项目一：监管报送数据中台

把散在核心、征信、外部数据源的数据，加工成一份**所有报表都能复算**的底座。

## 分层

| 层 | 职责 | 关键动作 |
|---|---|---|
| ODS | 贴源，保留原始字段 | 全量初始化 + 业务主键加时间戳增量，重跑不重复 |
| DWD | 明细清洗与标准化 | 空值/异常值/重复处理，借贷平衡与表内校验 |
| DM | 集市与指标 | 维度建模，信贷主题宽表，EAST / 1104 / 人行报送统一取数 |

## 关键设计

**增量幂等**：增量水位取 `max(updated_at)`，落库按 `business_key` 做 upsert，
并且只在 `excluded.updated_at > 现有值` 时才覆盖。补数、重跑、回滚都只需重放同一批次。

**校验前置**：校验不通过不上报。规则分三层——字段级（非空/枚举/区间）、表内（主键唯一、
借贷平衡）、表间（明细与汇总勾稽）。报告按「断言通过数 / 断言总数」计算通过率。

**调度闭环**：DAG 拓扑执行，节点级失败重试，重试耗尽告警并跳过下游，已成功的节点不重复跑。

## 代码结构

```
dp/config.py      # 数据源与表规格（字段、主键、增量水位、校验约束）
dp/extract.py     # 全量/增量抽取、upsert 合并
dp/clean.py       # 清洗与标准化
dp/validate.py    # 三层校验与通过率
dp/metrics.py     # DM 指标（不良率、逾期率、拨备覆盖率）
dp/scheduler.py   # DAG 调度、重试、告警
dp/pipeline.py    # 端到端演示
sql/              # ODS / DWD / DM 的 PostgreSQL 建表与 upsert 语句
```

## 运行

```bash
PYTHONPATH=data_platform python -m dp.pipeline --demo
PYTHONPATH=data_platform python -m dp.pipeline --demo --dirty-rows 40   # 注入更多脏数据看校验拦截
```

## 效果

一次校验通过率 60% → 98%+，每期准备工时 6 小时 → 1 小时以内（真实项目数据；
本仓库演示为合成数据，指标含义一致）。
