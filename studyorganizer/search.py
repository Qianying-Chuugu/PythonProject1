"""search 模块：三种检索 + 混合。

1. 语义检索：把文字变成向量，找意思最相近的文件（不要求出现相同关键词）。
2. 正文关键词检索：用 TF-IDF，找正文里字面匹配关键词的文件。
3. 混合检索：把上面几种（含标题关键词）各自归一化后加权合成一个总分。
"""

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
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


def search_semantic(query, top_k=5, min_score=0.3):
    """
    语义搜索：返回和 query 意思最相近的 top_k 个文件。
    参数 min_score：相似度下限，低于它的直接丢掉（0~1，越大越严格）。
    返回 [(标题, 相似度, 原因), ...]，相似度从高到低。
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

    pairs = [(t, s) for t, s in zip(titles, scores) if s >= min_score]  # 相似度太低 = 不相关，丢掉
    pairs.sort(key=lambda p: p[1], reverse=True)  # 按分数从高到低排
    # 每个结果附一句"为什么匹配"：方法名 + 命中详情。

    results = []
    for t, s in pairs[:top_k]:
        s = round(float(s), 3)
        results.append((t, s, f"语义检索：意思相近（相似度 {s}）"))
    return results


def search_keyword(query, top_k=5):
    """
    正文关键词检索：用 TF-IDF 找正文里字面匹配关键词的文件。
    返回 [(标题, 分数, 原因), ...]，分数从高到低。
    """
    rows = store.list_file_texts()
    if not rows:
        return []

    titles = [r[1] for r in rows]           # 所有标题
    texts = [r[2] for r in rows]            # 所有正文

    # 中文没空格，默认"按空格切词"不适用。
    # analyzer="char" 改成按字切；ngram_range=(2, 3) 表示切成相邻的 2~3 个字，如「动态规划」→「动态」「态规」「规划」「动态规」「态规划」
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 3))
    doc_vecs = vectorizer.fit_transform(texts)    # 每篇正文 → TF-IDF 向量
    query_vec = vectorizer.transform([query])     # 问题 → 同一种向量
    scores = cosine_similarity(query_vec, doc_vecs)[0]   # 每篇的匹配分（0 = 完全没匹配）

    pairs = [(t, s) for t, s in zip(titles, scores) if s > 0]  # 分数为 0 的说明没匹配上，丢掉
    pairs.sort(key=lambda p: p[1], reverse=True)               # 按分数从高到低排
    return [(t, round(s, 3), f"正文关键词匹配（TF-IDF 分数 {round(s, 3)}）") for t, s in pairs[:top_k]]


def _normalize(hits):
    """
    把 {标题: (分数, 原因)} 归一化：该方法里的最高分当作 1.0，其余按比例缩。
    这样三种方法的"第一名"都是 1.0，量纲统一，才能加权相加。
    """
    if not hits:
        return {}
    top = max(score for score, _reason in hits.values())
    if top == 0:                               # 全是 0 分，没法归一（避免除以 0），原样返回
        return hits
    return {title: (score / top, reason) for title, (score, reason) in hits.items()}


def search_hybrid(query, top_k=5, w_title=1.0, w_keyword=1.0, w_semantic=1.0):
    """
    混合检索：三种方法各自归一化后，加权合成一个总分。
    参数 w_*：三种方法的权重（默认等权 1.0；调大某个 = 更信那种方法）。
    返回 [(标题, 总分, 原因), ...]，总分从高到低；原因用「；」连接多个方法。
    """
    _ALL = 10 ** 6   # 传一个很大的 top_k = "全都要"（归一化得看到该方法的最高分）

    # ① 三种方法各自收集：{标题: (分数, 原因)}
    title_hits = {}
    for _id, path, title, reason in store.search_files(query):
        title_hits[title] = (1.0, reason)      # 标题搜索没有分数，命中即满分 1.0

    keyword_hits = {}
    for title, score, reason in search_keyword(query, top_k=_ALL):
        keyword_hits[title] = (score, reason)

    semantic_hits = {}
    for title, score, reason in search_semantic(query, top_k=_ALL):
        semantic_hits[title] = (score, reason)

    # ② 各自归一化后，按权重累加到 merged：{标题: [总分, [原因, ...]]}
    merged = {}
    for hits, weight in (
        (title_hits, w_title),
        (keyword_hits, w_keyword),
        (semantic_hits, w_semantic),
    ):
        for title, (score, reason) in _normalize(hits).items():
            if title not in merged:
                merged[title] = [0.0, []]      # [总分, 原因列表]
            merged[title][0] += weight * score
            merged[title][1].append(reason)    # 被几个方法命中，就有几条原因

    # ③ 按总分从高到低排，取前 top_k

    results = [(title, round(float(total), 3), "；".join(reasons)) for title, (total, reasons) in merged.items()]
    results.sort(key=lambda r: r[1], reverse=True)
    return results[:top_k]
