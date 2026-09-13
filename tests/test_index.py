"""测 index 模块：哪些文件的向量需要重算。

这里用真的 SQLite 库（tmp_path 里的临时文件），因为要测的正是
「store 和 index 配合起来，过期判断对不对」——把 store 换成假的就测不出来了。

只有模型是假的（真模型要下载几百 MB，测试不该干这个）。
"""

import numpy as np
import pytest

from studyorganizer import index, store
from studyorganizer.search import MODEL_NAME


class _假模型:
    """假模型：不发网络请求，固定返回 [1.0, 0.0] 这个向量。

    顺便记一下被调用了几次——用来验证「没有过期的文件时，不该白白加载模型」。
    """

    def __init__(self):
        self.调用次数 = 0

    def encode(self, texts):
        self.调用次数 += 1
        return np.array([[1.0, 0.0]] * len(texts), dtype=np.float32)


def _建库(tmp_path):
    """在临时目录建一个空库，返回它的路径。"""
    db = str(tmp_path / "test.db")
    store.init_db(db)
    return db


def _存一个文件(db, path, text):
    """把一条记录存进库（相当于导入了一次这个文件）。"""
    store.save_file({"path": path, "title": path, "text": text}, db)


# ---------- 情况一：没有过期 → 什么都不做 ----------

def test_全部是最新的就不加载模型(tmp_path, monkeypatch):
    db = _建库(tmp_path)
    _存一个文件(db, "a.txt", "正文")

    # 手动把它标成「已经用当前模型算好了」
    file_id = store.list_file_texts(db)[0][0]
    向量 = np.array([1.0, 0.0], dtype=np.float32).tobytes()
    store.save_embedding(file_id, 向量, MODEL_NAME, db)

    假模型 = _假模型()
    monkeypatch.setattr(index, "get_model", lambda: 假模型)

    assert index.ensure_embeddings(db) == 0     # 一条都不用算
    assert 假模型.调用次数 == 0                  # 关键：模型都没被碰过


# ---------- 情况二：还没算过 → 补上 ----------

def test_没向量的文件会补上(tmp_path, monkeypatch):
    db = _建库(tmp_path)
    _存一个文件(db, "a.txt", "正文")

    monkeypatch.setattr(index, "get_model", lambda: _假模型())

    assert index.ensure_embeddings(db) == 1
    # 补完之后，语义检索和聚类就得看得见它了
    assert len(store.list_file_vectors(db)) == 1


# ---------- 情况三：正文变了 → 作废重算 ----------

def test_正文变了向量作废要重算(tmp_path, monkeypatch):
    db = _建库(tmp_path)
    _存一个文件(db, "a.txt", "第一版正文")

    monkeypatch.setattr(index, "get_model", lambda: _假模型())
    index.ensure_embeddings(db)
    assert len(store.list_file_vectors(db)) == 1     # 先算好一份

    _存一个文件(db, "a.txt", "第二版正文")           # 改了正文，再存一次

    # save_file 里那句 CASE WHEN 应该把旧向量清掉，不然检索会拿到过期的向量
    assert store.list_file_vectors(db) == []

    assert index.ensure_embeddings(db) == 1          # 于是被重算
    assert len(store.list_file_vectors(db)) == 1


def test_正文没变就不会重算(tmp_path, monkeypatch):
    db = _建库(tmp_path)
    _存一个文件(db, "a.txt", "正文")

    假模型 = _假模型()
    monkeypatch.setattr(index, "get_model", lambda: 假模型)
    index.ensure_embeddings(db)

    _存一个文件(db, "a.txt", "正文")     # 原样再存一次（同一篇文档重复导入的场景）

    assert index.ensure_embeddings(db) == 0
    assert 假模型.调用次数 == 1           # 还是只算过最开始那一次


# ---------- 情况四：换了模型 → 全部重算 ----------

def test_换了模型全部重算(tmp_path, monkeypatch):
    db = _建库(tmp_path)
    _存一个文件(db, "a.txt", "正文A")
    _存一个文件(db, "b.txt", "正文B")

    monkeypatch.setattr(index, "get_model", lambda: _假模型())
    index.ensure_embeddings(db)

    # 假装模型换了一个。这条不是纸上谈兵：项目真的换过一次模型
    # （text2vec-base-chinese → bge-small-zh-v1.5），靠的就是下面这条判断把
    # 库里的旧向量全部作废重算，一行迁移代码都没写。
    monkeypatch.setattr(index, "MODEL_NAME", "另一个模型")

    # 旧向量是旧模型算的，和新模型的向量不在同一个空间里，比对没有意义 → 全都要重算
    assert index.ensure_embeddings(db) == 2


# ---------- import_and_index：导入完顺手建索引 ----------

def test_导入并建索引(tmp_path, monkeypatch):
    src = tmp_path / "资料"
    src.mkdir()
    (src / "讲义1.txt").write_text("动态规划", encoding="utf-8")
    (src / "笔记2.txt").write_text("英语单词", encoding="utf-8")

    db = str(tmp_path / "test.db")
    monkeypatch.setattr(index, "get_model", lambda: _假模型())

    n = index.import_and_index(str(src), db)

    assert n == 2
    assert len(store.list_file_vectors(db)) == 2     # 文档向量（聚类用），导入完立刻就能用上
    assert len(store.list_chunk_vectors(db)) == 2    # 段落向量（检索用）也一样


# ---------- 段落级向量：ensure_chunk_embeddings ----------

def test_切段并算好段落向量(tmp_path, monkeypatch):
    db = _建库(tmp_path)
    _存一个文件(db, "a.txt", "第一段。\n\n第二段。")

    monkeypatch.setattr(index, "get_model", lambda: _假模型())

    assert index.ensure_chunk_embeddings(db) == (1, 2)   # 切了 1 篇，算了 2 段
    # 段号从 1 开始，而且顺序就是原文顺序
    assert [r[2] for r in store.list_chunk_vectors(db)] == [1, 2]


def test_切过的文件不会重复切(tmp_path, monkeypatch):
    db = _建库(tmp_path)
    _存一个文件(db, "a.txt", "第一段。\n\n第二段。")

    假模型 = _假模型()
    monkeypatch.setattr(index, "get_model", lambda: 假模型)
    index.ensure_chunk_embeddings(db)

    # 再跑一次：段落都切好了、向量也都在 → 一件都不用做
    assert index.ensure_chunk_embeddings(db) == (0, 0)
    assert 假模型.调用次数 == 1                        # 模型都没被碰过


def test_正文变了段落会重切(tmp_path, monkeypatch):
    db = _建库(tmp_path)
    _存一个文件(db, "a.txt", "第一段。\n\n第二段。")

    monkeypatch.setattr(index, "get_model", lambda: _假模型())
    index.ensure_chunk_embeddings(db)
    assert len(store.list_chunk_vectors(db)) == 2

    _存一个文件(db, "a.txt", "改成只有一段了。")      # 正文改了

    # save_file 应该已经把按旧正文切出来的段落整批删掉了
    assert store.list_chunk_vectors(db) == []

    # 重新切、重新算：新正文只有一个自然段
    assert index.ensure_chunk_embeddings(db) == (1, 1)
    assert [r[3] for r in store.list_chunk_vectors(db)] == ["改成只有一段了。"]


def test_换了模型段落向量全部重算(tmp_path, monkeypatch):
    db = _建库(tmp_path)
    _存一个文件(db, "a.txt", "第一段。\n\n第二段。")

    monkeypatch.setattr(index, "get_model", lambda: _假模型())
    index.ensure_chunk_embeddings(db)

    monkeypatch.setattr(index, "MODEL_NAME", "另一个模型")

    # 段落本身不用重切（0 篇），但向量是旧模型算的，两段都要重算
    assert index.ensure_chunk_embeddings(db) == (0, 2)


def test_正文是空的文件不切段(tmp_path, monkeypatch):
    db = _建库(tmp_path)
    _存一个文件(db, "扫描件.pdf", "   \n  ")     # 模拟扫描件：提取出来没有文字

    monkeypatch.setattr(index, "get_model", lambda: _假模型())

    assert index.ensure_chunk_embeddings(db) == (0, 0)    # 没内容可切，也不算向量
    assert store.list_chunk_vectors(db) == []
