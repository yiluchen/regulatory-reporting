# 银行监管报送 · 数据与 AI 全链路

一条链路走完监管报送的四件事：**数据（数仓）→ 知识（模型 + RAG）→ 流程（Agent）→ 治理（Harness）**。
四个项目可独立运行，也可串起来看：数据中台是共同底座，领域模型在其上建知识库，ReportAgent 消费数据与知识，
Agent Harness 为所有 Agent 提供统一的运行时控制与审计。

| 项目 | 目录 | 解决什么问题 | 关键技术 | 可量化结果（引自各项目 README） |
|---|---|---|---|---|
| 01 数据中台 | `data_platform/` | 数据散、脏，跨报表口径对不上 | ODS/DWD/DM 分层建模、业务主键 upsert 增量幂等、三级校验、DAG 调度重试 | 校验通过率 60% → 98%+；每期准备工时 6 小时 → 1 小时以内（真实项目数据） |
| 02 领域模型 + RAG | `domain_llm/` | 专家逐条解读发文，通用模型容易乱编 | Qwen3-14B LoRA SFT→DPO、BGE-M3 三阶段检索（向量 + BM25 + 重排）、四道防幻觉闸门 | 召回率 75% → 92%，精确率 60% → 88%；单条解读 50 分钟 → 5 分钟以内 |
| 03 ReportAgent | `report_agent/` | 一问一答撑不起长链政策研究 | LangGraph 双线编排、七节点研究流程、双路检索与证据裁判、两级语义缓存、分层记忆 | 缓存命中首字 3.2s → 80ms；研究报告引用准确率约 94% |
| 04 Agent Harness | `agent_harness/` | Agent 越自主，越不敢放手 | 模型可插拔、工具登记制、控制点四类处置、只读 SQL 沙箱、七要素审计 | 新增工具 0 行业务改动；控制点误拦率低于 2%，运行全程可回放 |

> 表中数字为各项目 README 记录的项目实测或真实项目数据；本仓库的演示统一使用合成数据。

## 目录结构

```
regulatory-reporting/
├── README.md
├── requirements.txt
├── pytest.ini
├── docker-compose.yml
├── data_platform/          # 01 数据中台
│   ├── dp/                 #    抽取 / 清洗 / 校验 / 指标 / 调度 / 合成数据
│   ├── sql/                #    ODS / DWD / DM 建表与 upsert
│   ├── config/             #    数据源与表规格
│   └── tests/
├── domain_llm/             # 02 领域模型 + RAG
│   ├── dl/                 #    分块 / 稀疏 / 向量 / 融合 / 精排 / 护栏 / 数据构造
│   ├── configs/            #    QLoRA 8B、LoRA 14B SFT、DPO 训练配置
│   ├── data/               #    示例制度文本与检索评测集（合成）
│   └── tests/
├── report_agent/           # 03 ReportAgent
│   ├── ra/                 #    状态图 / 七节点 / 缓存 / 记忆 / 检索 / MCP / API
│   └── tests/
└── agent_harness/          # 04 Agent Harness
    ├── harness/            #    模型适配 / 工具注册 / 控制点 / 沙箱 / 审计 / Loop
    ├── config/             #    风险规则表与工具台账（YAML）
    └── tests/
```

## 快速开始

已在 Python 3.14 上验证。离线 demo 与测试只依赖 `pytest`、`PyYAML`。

```bash
# 安装依赖（如需真实服务/GPU，见 requirements.txt 中注释掉的可选依赖）
python3 -m pip install -r requirements.txt

# 全量单元测试（四个项目）
python3 -m pytest -q
```

四个 demo 都在仓库根目录执行，必须带 `PYTHONPATH` 指向对应项目目录：

```bash
# 01 数据中台：端到端跑 ODS → DWD → DM + 校验 + 增量重放 + 调度
PYTHONPATH=data_platform python3 -m dp.pipeline --demo
PYTHONPATH=data_platform python3 -m dp.pipeline --demo --dirty-rows 40   # 注入更多脏数据看校验拦截

# 02 领域模型 + RAG：建库后跑检索评测（离线哈希向量兜底，不需要 GPU）
PYTHONPATH=domain_llm python3 -m dl.scripts.build_kb --docs domain_llm/data/docs --out /tmp/kb.jsonl
PYTHONPATH=domain_llm python3 -m dl.scripts.eval_retrieval --docs domain_llm/data/docs

# 03 ReportAgent：离线跑研究线七节点、证据裁判与两级缓存命中
PYTHONPATH=report_agent python3 -m ra.demo

# 04 Agent Harness：四种控制点处置 + 审计回放
PYTHONPATH=agent_harness python3 -m harness.demo
```

接口服务需要安装 `requirements.txt` 中的「接口与服务」可选依赖：

```bash
uvicorn ra.api:app --app-dir report_agent                          # FastAPI + SSE
PYTHONPATH=report_agent python3 -m ra.mcp_server                    # MCP 工具服务

docker compose up -d      # 接真实服务时：PostgreSQL(pgvector) / Redis / Neo4j
```

## 设计取舍

1. **原始数据不出内网**。仓库只处理脱敏加工数据与公开发文，真实微调与推理都留在行内 GPU，示例全部用合成数据。
2. **不让模型决定权限**。工具调用先过控制点、再进只读沙箱，处置是规则表 + 代码判定，不是提示词里的自我约束。
3. **审计由 Harness 写**。每个工具调用都由运行时记录七要素（谁、什么模型、调了什么、结论、数据版本等），Agent 无法跳过。
4. **口径与表达分开**。RAG 管口径，政策变化换知识库即可生效；微调只管表达规范，不因一次口径调整重训模型。
5. **默认离线可跑**。向量与重排均有离线兜底实现，接口与线上一致，无 GPU、无外网也能跑通测试和 demo。

## 数据与合规声明

仓库内所有样例数据均为**合成数据**，制度文档为按公开监管文体编写的**示例文本**；
不含任何真实客户信息、真实账户数据、未公开监管信息或密钥。
真实落地时原始数据留在行内，本仓库仅演示脱敏加工数据与公开信息的处理链路。
