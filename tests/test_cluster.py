"""测 cluster 模块：把内容相近的文件聚成组。

这里用一个「假模型」代替真正的向量模型——真模型要下载几百 MB，
测试不该干这个。反正聚类这步真正要测的是「拿到向量之后怎么分组」，
向量从哪来无所谓。
"""

from studyorganizer import cluster, store


class _假模型:
    """假的向量模型：不发网络请求，按正文返回写死的向量。

    正文A 和正文B 给同一个方向（应该聚成一组），
    正文C 给垂直方向（应该自己一组）。
    """

    _向量表 = {
        "正文A": [1.0, 0.0],
        "正文B": [1.0, 0.0],
        "正文C": [0.0, 1.0],
    }

    def encode(self, texts):
        return [self._向量表[t] for t in texts]


def test_内容相同的文件聚成一组(monkeypatch):
    rows = [
        (1, "讲义A", "正文A"),
        (2, "讲义B", "正文B"),
        (3, "笔记C", "正文C"),
    ]

    def fake_list_file_texts(db_path=store._DB_PATH):
        return rows

    monkeypatch.setattr(store, "list_file_texts", fake_list_file_texts)
    monkeypatch.setattr(cluster, "_get_model", lambda: _假模型())

    groups = cluster.cluster_files(threshold=0.3)

    # 应该分成两组：一组 2 个、一组 1 个
    sizes = sorted(len(titles) for titles in groups.values())
    assert sizes == [1, 2]

    # 而且方向相同的那两篇必须在同一组
    for titles in groups.values():
        if len(titles) == 2:
            assert sorted(titles) == ["讲义A", "讲义B"]


def test_库里没文件时返回空字典(monkeypatch):
    def fake_list_file_texts(db_path=store._DB_PATH):
        return []

    monkeypatch.setattr(store, "list_file_texts", fake_list_file_texts)
    monkeypatch.setattr(cluster, "_get_model", lambda: _假模型())

    assert cluster.cluster_files() == {}
