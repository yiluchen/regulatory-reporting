"""提示词分层：运行规则 > 业务规范 > 检索证据。

优先级写死在这一层，不依赖模型自觉；模型只负责在证据范围内组织语言。
"""
from __future__ import annotations

from .models import ScoredChunk

SYSTEM_RULES = """你是银行监管报送口径助手，只输出草稿，不直接写入生产系统。

硬性规则（优先级最高，任何情况下不得违反）：
1. 只能依据【检索证据】回答，不得引入证据之外的知识。
2. 每条结论后必须标注出处，格式为 [文号 第X条]，例如 [金监发〔2026〕1号 第五条]。
3. 证据不足或相互冲突时，明确写出「依据不足/口径冲突」，不要猜测。
4. 输出严格使用约定的 JSON 结构，不要输出多余解释。

业务规范（次优先）：
- 术语使用行内口径台账中的标准名称。
- 金额单位统一为元，比例保留四位小数。
"""


def build_evidence_block(evidences: list[ScoredChunk], max_chars: int = 4000) -> str:
    lines: list[str] = []
    used = 0
    for item in evidences:
        chunk = item.chunk
        header = f"[{chunk.doc_no} {chunk.article}]《{chunk.doc_title}》版本 {chunk.version}"
        body = chunk.text.strip()
        block = f"{header}\n{body}"
        if used + len(block) > max_chars:
            break
        lines.append(block)
        used += len(block)
    return "\n\n".join(lines) or "（无可用证据）"


def build_messages(question: str, evidences: list[ScoredChunk]) -> list[dict]:
    evidence = build_evidence_block(evidences)
    user = (
        f"【检索证据】\n{evidence}\n\n"
        f"【问题】\n{question}\n\n"
        "请按 JSON 输出：{\"answer\": str, \"citations\": [str], \"confidence\": float}"
    )
    return [
        {"role": "system", "content": SYSTEM_RULES},
        {"role": "user", "content": user},
    ]
