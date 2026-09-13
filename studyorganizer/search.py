"""search 模块：三种检索 + 混合。

1. 语义检索：把每一段文字变成向量，找意思最相近的文件（不要求出现相同关键词）。
   按段落比而不是整篇比，长文档里的细节才不会被"平均"掉。
2. 正文关键词检索：用 TF-IDF，找正文里字面匹配关键词的文件。
3. 混合检索：把上面几种（含标题关键词）各自归一化后加权合成一个总分。
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from studyorganizer import store

MODEL_NAME = "BAAI/bge-small-zh-v1.5"   # index.py 也要用它判断向量有没有过期
_model = None

def get_model():
    """加载模型（第一次调用时才真正加载，之后复用）。"""
    global _model
    if _model is None:
        # 延迟导入：sentence_transformers 会连带拉进 torch，很重（光 import 就要好几秒）。
        # 写在函数里，只有真正要用模型时才付这笔开销。见 NOTES.md 第 4 条。
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


_TOP_N = 3          # 算文件分时，最多拿最好的几段来平均


def _snippet(text, limit=40):
    """截一小段正文给人看，太长了加省略号。"""
    return text[:limit] + ("…" if len(text) > limit else "")


def search_semantic(query, top_k=5, min_score=0.45):
    """
    语义搜索：返回和 query 意思最相近的 top_k 个文件。
    参数 min_score：段落相似度下限，低于它的段落直接丢掉（0~1，越大越严格）。
    返回 [(标题, 分数, 原因), ...]，分数从高到低。

    关于默认门槛 0.45：这是**实测**出来的，不是拍的，而且随时能自己重跑验证
    ——`python tools/benchmark.py`（数字和对照表在 DESIGN.md）。
    bge-small 给出的相似度同样会"压缩"（跟查询无关的段落大多落在 0.2~0.55），
    但比原来用的 text2vec 好得多：同样卡 0.45，text2vec 放行 46% 的段落（阈值形同
    虚设），bge-small 只放行 23%；正确答案的文件分大约在 0.53~0.89。
    换模型时**刻意没有重调这个数**，也没打算靠调它来提升效果——它不是一个
    "越高越严"的旋钮：21 条测试查询里，0.45~0.60 都是 21/21，调高到 0.65 崩到 17/21
    （答案段落被整条砍掉），**调低到 0.30/0.40 反而掉到 20/21**。原因是 min_score
    不只是过滤器，它还决定"前 3 段平均"从哪些段里取，放宽会把文件分拖下来。
    0.45 的定位始终只是"砍掉明显跑题的尾部"；真正决定顺序的是排序，
    不是这个阈值（实测过不相关段落的分数比答案段落还高的情况）。
    改完这个文件请跑 `python tools/benchmark.py --check`。

    为什么按段落算：长文档整篇压成一个向量会把细节"平均"掉。一篇 30 页的讲义里
    只有一段讲了背包问题，整篇的向量跟"背包问题"并不像，整篇算就搜不到；
    按段落算才能精确命中讲那段话的地方。
    """
    # 只要当前模型的段落向量：库里可能残留别的模型算的（换模型重算到一半被打断），
    # 那些维度不一样，混进来一起算余弦会直接崩。
    rows = store.list_chunk_vectors(MODEL_NAME)   # [(文件id, 标题, 段号, 段落正文, 向量), ...]
    if not rows:
        return []                       # 库是空的（或还没建索引）就直接返回

    titles = [r[1] for r in rows]
    seqs = [r[2] for r in rows]
    texts = [r[3] for r in rows]
    # 裸字节必须按当初的 float32 还原。存的时候怎么写的，这里就得怎么读——
    # 类型写错不会报错，只会读出一堆垃圾数字。用 vstack 顺便拼成二维数组。
    chunk_vecs = np.vstack([np.frombuffer(r[4], dtype=np.float32) for r in rows])

    model = get_model()
    query_vec = model.encode([query])   # 问题 → 向量（查询词每次现算，没存过）
    scores = cosine_similarity(query_vec, chunk_vecs)[0]

    # ① 丢掉"不沾边"的段落，再按文件分组。
    #    这一步是关键：低分段落绝不能算进下面的平均分，否则一篇"只有一段
    #    讲对了"的好文件会被周围一堆 0.1 分的废话拉垮，反而排不上来。
    #    （严格说，先过滤再取前 3 和先取前 3 再过滤结果是一样的——过滤是
    #      按分数线切的，排序又保证够格的都排在不够格的前面，两者可以交换。
    #      所以别纠结顺序，重点是这一步必须做。）
    per_file = {}                       # {标题: [(分数, 段号, 段落正文), ...]}
    for title, seq, text, score in zip(titles, seqs, texts, scores):
        if score >= min_score:
            per_file.setdefault(title, []).append((float(score), seq, text))

    # ② 一个文件的分数 = 它最好的前 3 段的平均分。
    #    取平均而不是取最高分：既奖励"有一段特别准"，也奖励"好几段都相关"，
    #    而且不像取最高分那样偏向段落多的长文档（段落多，蒙中高分的机会就多）。
    results = []
    for title, hits in per_file.items():
        hits.sort(key=lambda h: h[0], reverse=True)
        top = hits[:_TOP_N]
        score = sum(h[0] for h in top) / len(top)

        best_score, best_seq, best_text = hits[0]     # 分数最高的那段拿来解释
        reason = (f"语义检索：第 {best_seq} 段最相近（相似度 {best_score:.3f}）"
                  f"「{_snippet(best_text)}」")
        if len(hits) > 1:
            # 文件分是平均来的，不说明一下的话用户会觉得"为什么分数比上面低"
            reason += f"；文件分 = 最好的 {len(top)} 段平均（全文共 {len(hits)} 段相关）"
        results.append((title, round(score, 3), reason))

    results.sort(key=lambda r: r[1], reverse=True)
    return results[:top_k]


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
