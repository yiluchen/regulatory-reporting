"""SFT / DPO 数据构造：去重、按问题哈希切分、防泄漏。"""
from __future__ import annotations

import hashlib
import re
from collections import Counter

SYSTEM_PROMPT = "你是银行监管报送口径助手，只依据给定条款作答，并标注 [文号 第X条]。"


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower())


def dedup(items: list[dict], key: str = "question") -> tuple[list[dict], int]:
    seen: set[str] = set()
    kept: list[dict] = []
    for item in items:
        k = _norm(str(item.get(key, "")))
        if k in seen:
            continue
        seen.add(k)
        kept.append(item)
    return kept, len(items) - len(kept)


def build_sft(items: list[dict]) -> list[dict]:
    samples = []
    for item in items:
        samples.append(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": item["question"]},
                    {"role": "assistant", "content": item["answer"]},
                ]
            }
        )
    return samples


def build_dpo(pairs: list[dict]) -> list[dict]:
    samples = []
    for pair in pairs:
        samples.append(
            {
                "system": SYSTEM_PROMPT,
                "prompt": pair["question"],
                "chosen": pair["chosen"],
                "rejected": pair["rejected"],
            }
        )
    return samples


def split_train_test(
    items: list[dict], test_ratio: float = 0.1, seed: str = "2026", key: str = "question"
) -> tuple[list[dict], list[dict]]:
    """按问题文本哈希分桶，保证同一问题只出现在一侧，避免考原题。"""
    train: list[dict] = []
    test: list[dict] = []
    for item in items:
        k = _norm(str(item.get(key, "")))
        bucket = int(hashlib.sha1(f"{seed}:{k}".encode("utf-8")).hexdigest(), 16) % 1000
        (test if bucket < int(test_ratio * 1000) else train).append(item)
    return train, test


def dataset_stats(items: list[dict], key: str = "question") -> dict:
    questions = Counter(_norm(str(i.get(key, ""))) for i in items)
    return {
        "total": len(items),
        "unique": len(questions),
        "duplicated": sum(v - 1 for v in questions.values() if v > 1),
    }
