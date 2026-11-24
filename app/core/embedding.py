"""Embedding 抽象。

生产环境替换为 OpenAI / 本地 bge 等 embedding 服务；默认 LocalEmbedding 是一个
确定性的哈希词袋向量，仅用于开发与单元测试，保证无外部 API 时语义相似度可计算。
"""
from __future__ import annotations

import hashlib
import math
import re

from app.core.config import settings

EMBED_DIM = 256
_STOPWORDS = {
    "的", "了", "和", "是", "在", "我", "有", "找", "查", "一下", "最近", "所有", "没有",
    "还", "不", "都", "吗", "呢", "the", "a", "an", "is", "are", "to", "of", "and",
    "find", "show", "me", "all", "recent",
}


def tokenize(text: str) -> list[str]:
    """英文按单词、中文按单字与相邻双字切分，兼顾英文型号与中文语义。"""
    text = text.lower()
    tokens: list[str] = re.findall(r"[a-z0-9]+", text)
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    tokens.extend(cjk)
    tokens.extend(cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1))
    return [t for t in tokens if t and t not in _STOPWORDS]


class LocalEmbedding:
    """词袋哈希到固定维度桶，L2 归一化；点积即余弦相似度。"""

    dim = EMBED_DIM

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in tokenize(text):
            bucket = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16) % self.dim
            vec[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            return vec
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def get_embedding_provider():
    if settings.embedding_provider == "local" or not settings.llm_api_key:
        return LocalEmbedding()
    # 生产占位：接入真实 embedding 服务，例如 OpenAI / bge 本地模型
    raise RuntimeError(
        f"embedding_provider={settings.embedding_provider} 需要配置 API key；"
        "开发阶段请使用 EMBEDDING_PROVIDER=local"
    )
