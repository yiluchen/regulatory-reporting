"""向量化：线上用 BGE-M3，离线用确定性哈希向量兜底。

接口保持一致（encode -> list[list[float]]），换成真实模型时上层无需改动。
"""
from __future__ import annotations

import hashlib
import math

from .sparse import tokenize


class HashingEmbedder:
    """离线兜底：字符 n-gram 哈希到固定维度。

    只用于无 GPU 环境下跑通链路与单元测试，不参与线上效果评估。
    """

    name = "hashing-fallback"

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in tokenize(text):
            idx = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class BGEM3Embedder:
    """BGE-M3 稠密向量（需要 sentence-transformers / FlagEmbedding）。"""

    name = "bge-m3"

    def __init__(self, model_path: str = "BAAI/bge-m3", device: str = "cuda", batch_size: int = 8) -> None:
        from FlagEmbedding import BGEM3FlagModel  # 延迟导入，离线环境不需要

        self.model = BGEM3FlagModel(model_path, use_fp16=(device == "cuda"))
        self.batch_size = batch_size

    def encode(self, texts: list[str]) -> list[list[float]]:
        output = self.model.encode(texts, batch_size=self.batch_size, max_length=1024)
        return [list(map(float, v)) for v in output["dense_vecs"]]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def build_embedder(offline: bool = False):
    """按环境构建 embedder：默认尝试 BGE-M3，失败或显式离线则降级。"""
    if offline:
        return HashingEmbedder()
    try:
        return BGEM3Embedder()
    except Exception:  # noqa: BLE001 - 无模型权重/无 GPU 时降级，不阻断流程
        return HashingEmbedder()
