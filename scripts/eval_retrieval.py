"""离线检索评测脚手架：Recall@K、MRR、nDCG@K、结构化解析准确率。

使用方式（自行准备标注集 labels.jsonl，每行一条）：
    {"query": "最近7天未解决的高优先级物流工单", "relevant": [12, 34]}
    {"query": "提到耳机断连的未结案例", "relevant": [56]}

对比三路召回：纯结构化、纯语义、融合结果；输出均值指标，用于调参与简历量化。
本脚本只提供指标计算与加载接口，具体数据集接入按你的业务工单填充。
"""
import json
import sys


def recall_at_k(ranked: list[int], relevant: set[int], k: int) -> float:
    hit = sum(1 for r in ranked[:k] if r in relevant)
    return hit / len(relevant) if relevant else 0.0


def mrr(ranked: list[int], relevant: set[int]) -> float:
    for idx, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / idx
    return 0.0


def _dcg(rels: list[int]) -> float:
    return sum(rel / (i + 1) for i, rel in enumerate(rels))


def ndcg_at_k(ranked: list[int], relevant: set[int], k: int) -> float:
    gains = [1 if r in relevant else 0 for r in ranked[:k]]
    ideal = sorted([1] * len(relevant), reverse=True)
    dcg = _dcg(gains)
    idcg = _dcg(ideal)
    return dcg / idcg if idcg else 0.0


def parse_accuracy(predicted: dict, expected: dict) -> float:
    """结构化解析准确率：逐字段比较枚举 / 时间 / 关键词集合，全对得 1，否则 0。"""
    correct = sum(
        1 for key in expected if predicted.get(key) == expected[key]
    )
    return correct / len(expected) if expected else 0.0


def load_labels(path: str) -> list[dict]:
    labels = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                labels.append(json.loads(line))
    return labels


def summarize(name: str, rows: list[tuple[list[int], set[int]]]) -> dict:
    recalls, mrrs, ndcgs = [], [], []
    for ranked, relevant in rows:
        recalls.append(recall_at_k(ranked, relevant, k=10))
        mrrs.append(mrr(ranked, relevant))
        ndcgs.append(ndcg_at_k(ranked, relevant, k=10))
    n = len(rows) or 1
    return {
        "strategy": name,
        "Recall@10": round(sum(recalls) / n, 4),
        "MRR": round(sum(mrrs) / n, 4),
        "nDCG@10": round(sum(ndcgs) / n, 4),
    }


if __name__ == "__main__":
    # 占位：接入 labels.jsonl 与三路召回结果后调用 summarize() 输出对比表
    if len(sys.argv) > 1:
        print(f"标注集路径：{sys.argv[1]}（请在脚本内接入召回结果后运行）")
    else:
        print("用法：python scripts/eval_retrieval.py labels.jsonl")
