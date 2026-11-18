"""建库脚本：文档 → 条款分块 → 向量化（此处落 jsonl，线上写 pgvector）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dl.embedding import build_embedder
from dl.loader import chunk_to_dict, load_chunks, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default="domain_llm/data/docs")
    parser.add_argument("--out", default="/tmp/kb.jsonl")
    parser.add_argument("--offline", action="store_true", help="使用离线哈希向量")
    args = parser.parse_args()

    chunks = load_chunks(args.docs)
    if not chunks:
        print("没有找到文档", file=sys.stderr)
        raise SystemExit(1)

    embedder = build_embedder(offline=args.offline)
    vectors = embedder.encode([c.embed_text() for c in chunks])
    rows = []
    for chunk, vec in zip(chunks, vectors):
        row = chunk_to_dict(chunk)
        row["embedding_model"] = embedder.name
        row["vector_dim"] = len(vec)
        rows.append(row)

    write_jsonl(args.out, rows)
    docs = {c.doc_no for c in chunks}
    print(f"文档 {len(docs)} 篇，条款 {len(chunks)} 条，向量模型 {embedder.name}，已写入 {args.out}")


if __name__ == "__main__":
    main()
