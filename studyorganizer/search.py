"""search 模块：语义检索。

把文字变成向量，找和问题意思最相近的文件（不要求出现相同关键词）。
"""

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from studyorganizer import store

_MODEL_NAME = "shibing624/text2vec-base-chinese"
_model = None

def _get_model():
    """加载模型（第一次调用时才真正加载，之后复用）。"""
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def search_semantic(query, top_k=5):
    """
    语义搜索：返回和 query 意思最相近的 top_k 个文件。
    返回 [(标题, 相似度), ...]，相似度从高到低。
    """
    model = _get_model()
    rows = store.list_file_texts()
    if not rows:
        return []

    titles = [r[1] for r in rows]           # 所有标题
    texts = [r[2] for r in rows]            # 所有正文

    query_vec = model.encode([query])       # 问题 → 向量
    doc_vecs = model.encode(texts)          # 每篇正文 → 向量
    scores = cosine_similarity(query_vec, doc_vecs)[0]  # 每篇的相似度 0-1,此处生成的余弦相似度只有一行

    pairs = list(zip(titles, scores))       # (标题, 分数) 两两配对
    pairs.sort(key=lambda p: p[1], reverse=True)  # 按分数从高到低排
    return [(t, round(s, 3)) for t, s in pairs[:top_k]]
