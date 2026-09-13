"""cluster 模块：把内容相近的文件聚成组。

用层次聚类（AgglomerativeClustering），把语义相近的文件归到同一堆。
这是"整理方案"的基础：同一堆的文件，将来建议放到一起。

向量不用现算——直接从库里读 index 模块存好的那些，所以这里不需要模型。
"""

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from studyorganizer import store


def cluster_files(threshold=0.3):
    """
    把数据库里的文件按内容相似度聚成若干组。
    参数 threshold：距离阈值，越大合并越狠、堆越少（余弦距离 0~1）。
    返回 {堆号: [标题列表], ...}
    """
    rows = store.list_file_vectors()
    if not rows:
        return {}                           # 库是空的（或还没建索引）就直接返回

    titles = [r[1] for r in rows]
    # 和 search_semantic 一样：裸字节必须按当初的 float32 还原
    vecs = np.vstack([np.frombuffer(r[2], dtype=np.float32) for r in rows])

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
