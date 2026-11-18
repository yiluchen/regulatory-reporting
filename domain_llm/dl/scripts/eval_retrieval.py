"""检索评测脚本。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dl.evaluate import evaluate_retrieval
from dl.loader import load_chunks
from dl.retriever import HybridRetriever


def main() -> None:
    base = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default=str(base / "data" / "docs"))
    parser.add_argument("--cases", default=str(base / "data" / "eval_set.jsonl"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--offline", action="store_true", default=True)
    args = parser.parse_args()

    chunks = load_chunks(args.docs)
    retriever = HybridRetriever(chunks, offline=args.offline)
    cases = [json.loads(l) for l in Path(args.cases).read_text(encoding="utf-8").splitlines() if l.strip()]
    metrics = evaluate_retrieval(retriever, cases, k=args.k)
    print(json.dumps({k: v for k, v in metrics.items() if k != "misses"}, ensure_ascii=False, indent=2))
    for miss in metrics["misses"]:
        print("未命中:", miss["q"], "->", miss["got"][:3])


if __name__ == "__main__":
    main()
