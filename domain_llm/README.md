# 项目二：报送专用模型 + RAG 知识库

定位很明确：**AI 出草稿、专家终审**，全程只用脱敏数据和公开发文。

## 分工原则

| 手段 | 管什么 | 变了怎么办 |
|---|---|---|
| 微调（SFT → DPO） | 表达规范、输出结构、专家口吻 | 重新训练，低频 |
| RAG | 报送口径、制度原文、文号版本 | 换知识库，分钟级生效 |

两者刻意分开：口径调整不该触发一次训练，表达不规范也不该靠检索解决。

## 训练

1. 本地 Qwen3-8B + 4bit QLoRA 验证数据质量（一张 4090，一轮约 40 分钟）
2. 行内 GPU 上 Qwen3-14B 做 LoRA：先 SFT 学格式，再 DPO 学"哪个答案更好"
3. vLLM 部署为内网 OpenAI 兼容服务，业务侧按普通 HTTP 调用

选 DPO 不选 RLHF：不用单独训奖励模型，几百对偏好样本即可训稳。

## 检索

```
文档解析 → 按章节/条款分块（带文号、版本、生效日期）→ BGE-M3 向量化
        → pgvector + HNSW；同时建 BM25 稀疏索引
查询 → 稠密 top-20 ‖ 稀疏 top-20 → RRF 融合 → Cross-Encoder 精排 top-5 → 强制附出处
```

四个提精度手段：条款级分块、混合检索、Cross-Encoder 精排、查询扩展。
优化后召回率 75% → 92%，精确率 60% → 88%（项目实测）。

## 四道防幻觉闸门

| 闸门 | 规则 | 不通过 |
|---|---|---|
| 强制溯源 | 每句必须有检索到的条款支撑 | 检索为空直接拒答，不调模型 |
| 白名单 | 报表名、字段、部门必须能精确匹配 | 直接拦截 |
| JSON 结构 | 固定 schema | 重试 2 次后转人工 |
| 置信度 | 检索分 + 精排分 + 自评加权 | <0.6 转人工，>0.85 出草稿 |

最后一道是**草稿制**：模型账号只有草稿表写权限，生产表写权限只在审核服务手里。

## 代码结构

```
dl/chunking.py    # 条款级分块，保留文号/版本/生效日期
dl/sparse.py      # BM25（纯 Python，可离线跑）
dl/embedding.py   # BGE-M3 适配器 + 离线哈希兜底
dl/fusion.py      # RRF 融合
dl/rerank.py      # bge-reranker-v2-m3 适配器 + 词面兜底
dl/retriever.py   # 三阶段混合检索
dl/guardrails.py  # 四道闸门与置信度路由
dl/dataset.py     # SFT / DPO 数据构造、去重、防泄漏切分
dl/scripts/       # 建库、检索评测
configs/          # QLoRA 8B / LoRA 14B SFT / DPO 训练配置
```

## 运行

```bash
PYTHONPATH=domain_llm python -m dl.scripts.build_kb --docs domain_llm/data/docs --out /tmp/kb.jsonl
PYTHONPATH=domain_llm python -m dl.scripts.eval_retrieval --docs domain_llm/data/docs
```

不装 GPU 依赖也能跑：embedding 与 rerank 会自动降级为离线实现，接口与线上一致。

## 效果

专家盲评草稿分 2.1 → 4.3；口径命中率 72% → 98%；单条解读 50 分钟 → 5 分钟以内。
