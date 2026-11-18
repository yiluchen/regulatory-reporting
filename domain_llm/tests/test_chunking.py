"""条款分块：结构、元数据、可回溯。"""
from pathlib import Path

from dl.chunking import chunk_document
from dl.loader import load_chunks

DOCS = Path(__file__).resolve().parents[1] / "data" / "docs"

TEXT = """
## 第二章 风险分类

第三条 金融资产按照风险程度分为正常、关注、次级、可疑、损失五类。
后三类合称不良资产。

第四条 逾期天数为自然日天数。
"""


def test_split_by_article_keeps_metadata():
    chunks = chunk_document(
        TEXT, doc_no="金监发〔2026〕1号", doc_title="示例办法", version="v1.0",
        effective_date="2026-03-01",
    )
    assert [c.article for c in chunks] == ["第三条", "第四条"]
    assert chunks[0].doc_no == "金监发〔2026〕1号"
    assert chunks[0].version == "v1.0"
    assert chunks[0].effective_date == "2026-03-01"
    assert "第二章" in chunks[0].section


def test_article_text_not_split():
    chunks = chunk_document(TEXT, doc_no="X", doc_title="T", version="v1")
    assert "后三类合称不良资产" in chunks[0].text


def test_chunk_id_is_citable():
    chunks = chunk_document(TEXT, doc_no="X", doc_title="T", version="v1")
    assert chunks[0].chunk_id == "X#第三条"
    assert "第三条" in chunks[0].citation


def test_load_chunks_from_docs_dir():
    chunks = load_chunks(DOCS)
    assert len(chunks) >= 12
    assert {c.doc_no for c in chunks} == {"金监发〔2026〕1号", "行内口径〔2026〕07号"}
    assert all(c.status == "active" for c in chunks)
