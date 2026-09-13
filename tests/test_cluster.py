"""测 cluster 模块：把内容相近的文件聚成组。

聚类用的向量是从数据库里读的（index 模块算好存进去的那种）。
所以这里只要往「库」里塞几个假向量就够了——不用下载真模型，
也不用真的建库（把 store.list_file_vectors 换成假函数即可）。

这步真正要测的是「拿到向量之后怎么分组」，向量从哪来无所谓。
"""

import numpy as np

from studyorganizer import cluster, store

_假模型 = "假模型"   # cluster_files 要求指明按哪个模型的向量来聚


def _向量(*nums):
    """把一串数字打包成数据库里存的那种字节（float32 的 .tobytes()）。

    注意 dtype 必须和 index.py 存的时候一致，写错不会报错，只会读出垃圾数字。
    """
    return np.array(nums, dtype=np.float32).tobytes()


def test_内容相同的文件聚成一组(monkeypatch):
    # 讲义A 和 讲义B 方向相同（应该聚成一组），笔记C 垂直（自己一组）
    rows = [
        (1, "讲义A", _向量(1.0, 0.0)),
        (2, "讲义B", _向量(1.0, 0.0)),
        (3, "笔记C", _向量(0.0, 1.0)),
    ]

    def fake_list_file_vectors(model_name, db_path=store._DB_PATH):
        # 顺便看一眼它问的是哪个模型：真正的过滤逻辑在 store 里，这里只确认名字传下去了
        assert model_name == _假模型
        return rows

    monkeypatch.setattr(store, "list_file_vectors", fake_list_file_vectors)

    groups = cluster.cluster_files(_假模型, threshold=0.3)

    # 应该分成两组：一组 2 个、一组 1 个
    sizes = sorted(len(titles) for titles in groups.values())
    assert sizes == [1, 2]

    # 而且方向相同的那两篇必须在同一组
    for titles in groups.values():
        if len(titles) == 2:
            assert sorted(titles) == ["讲义A", "讲义B"]


def test_库里没向量时返回空字典(monkeypatch):
    def fake_list_file_vectors(model_name, db_path=store._DB_PATH):
        return []

    monkeypatch.setattr(store, "list_file_vectors", fake_list_file_vectors)

    # 聚类本身用不到向量模型，所以库空就直接返回，不需要额外兜底
    assert cluster.cluster_files(_假模型) == {}
