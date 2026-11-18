"""文档加载：front matter + 条款分块。"""
from __future__ import annotations

import json
from pathlib import Path

from .chunking import chunk_document
from .models import Chunk


def parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, parts[2].lstrip("\n")


def load_chunks(docs_dir: str | Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(Path(docs_dir).glob("*.md")):
        meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
        chunks.extend(
            chunk_document(
                body,
                doc_no=meta.get("doc_no", path.stem),
                doc_title=meta.get("title", path.stem),
                version=meta.get("version", "v1.0"),
                effective_date=meta.get("effective_date", ""),
                status=meta.get("status", "active"),
            )
        )
    return chunks


def chunk_to_dict(chunk: Chunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "doc_no": chunk.doc_no,
        "doc_title": chunk.doc_title,
        "version": chunk.version,
        "article": chunk.article,
        "section": chunk.section,
        "text": chunk.text,
        "effective_date": chunk.effective_date,
        "status": chunk.status,
    }


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
