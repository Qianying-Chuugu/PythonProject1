"""cluster 模块：把内容相近的文件聚成组。

用层次聚类（AgglomerativeClustering），把语义相近的文件归到同一堆。
这是"整理方案"的基础：同一堆的文件，将来建议放到一起。
"""

from sklearn.cluster import AgglomerativeClustering

from studyorganizer import store
from studyorganizer.search import _get_model   # 复用语义检索的模型


def cluster_files(threshold=0.3):
    """把数据库里的文件按内容相似度聚成若干组。

    参数 threshold：距离阈值，越大合并越狠、堆越少（余弦距离 0~1）。
    返回 {堆号: [标题列表], ...}
    """
    model = _get_model()
    rows = store.list_file_texts()
    if not rows:
        return {}

    titles = [r[1] for r in rows]
    texts = [r[2] for r in rows]

    vecs = model.encode(texts)
    labels = AgglomerativeClustering(
        n_clusters=None,           # 不限制堆数，让阈值决定
        distance_threshold=threshold,
        metric='cosine',           # 余弦距离（0=一样，1=完全不同）
        linkage='average',         # 平均连接
    ).fit_predict(vecs).tolist()

    groups = {}
    for title, label in zip(titles, labels):
        if label not in groups:
            groups[label] = []
        groups[label].append(title)

    return groups
