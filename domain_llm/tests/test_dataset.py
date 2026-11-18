"""SFT / DPO 数据构造与防泄漏切分。"""
from dl.dataset import build_dpo, build_sft, dedup, split_train_test


def _items(n: int = 40) -> list[dict]:
    return [
        {"question": f"问题{i}", "answer": f"答案{i}", "citations": ["X#第一条"]}
        for i in range(n)
    ]


def test_dedup_by_normalized_question():
    items = _items(3) + [{"question": " 问题0 ", "answer": "重复"}]
    kept, removed = dedup(items)
    assert removed == 1
    assert len(kept) == 3


def test_sft_format():
    samples = build_sft(_items(2))
    assert samples[0]["messages"][0]["role"] == "system"
    assert samples[0]["messages"][-1]["role"] == "assistant"


def test_dpo_format():
    pairs = [{"question": "q", "chosen": "好", "rejected": "差"}]
    sample = build_dpo(pairs)[0]
    assert {"system", "prompt", "chosen", "rejected"} <= set(sample)


def test_split_has_no_leakage():
    items = _items(100)
    train, test = split_train_test(items, test_ratio=0.2, seed="2026")
    assert train and test
    train_q = {i["question"] for i in train}
    test_q = {i["question"] for i in test}
    assert not (train_q & test_q)
    assert len(train) + len(test) == 100


def test_split_is_deterministic():
    a = split_train_test(_items(50), 0.2, "seed-a")
    b = split_train_test(_items(50), 0.2, "seed-a")
    assert [x["question"] for x in a[1]] == [x["question"] for x in b[1]]
