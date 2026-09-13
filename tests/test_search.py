"""测 search 模块里不依赖向量模型的部分。

注意：这些测试**都不会加载语义模型**（那要下载几百 MB，测试不该干这个）。
search_keyword 只用到 TF-IDF，search_hybrid 的三个来源我们用假函数替掉，
所以测的是「合并、归一化、加权」这套自己的逻辑。
"""

from studyorganizer import search, store
from studyorganizer.search import _normalize, search_hybrid, search_keyword


# ---------- _normalize：把每种方法的最高分缩成 1.0 ----------

def test_归一化_最高分变成1():
    # 归一化的目的：让三种方法量纲一致，才能加权相加
    hits = {"A": (2.0, "原因A"), "B": (1.0, "原因B")}
    result = _normalize(hits)

    assert result["A"][0] == 1.0      # 最高分 → 1.0
    assert result["B"][0] == 0.5      # 一半 → 0.5


def test_归一化_空字典返回空():
    assert _normalize({}) == {}


def test_归一化_全是零分时不会除以零():
    # 一种方法完全没命中时最高分是 0，直接相除会 ZeroDivisionError
    hits = {"A": (0.0, "没匹配")}
    assert _normalize(hits) == hits


# ---------- search_keyword：正文关键词检索 ----------

def test_正文关键词检索_只返回命中的文件(monkeypatch):
    rows = [
        (1, "动态规划讲义", "状态转移方程是动态规划的核心"),
        (2, "英语笔记", "今天背了单词"),
    ]

    def fake_list_file_texts(db_path=store._DB_PATH):
        return rows

    monkeypatch.setattr(store, "list_file_texts", fake_list_file_texts)

    results = search_keyword("动态规划")

    assert len(results) == 1                    # 「英语笔记」完全没匹配上，被丢掉
    assert results[0][0] == "动态规划讲义"
    assert "TF-IDF" in results[0][2]            # 第三项是给人看的「匹配原因」


# ---------- search_hybrid：混合检索 ----------

def _假装有三个来源(monkeypatch):
    """把 search_hybrid 依赖的三个来源换成写死的数据。

    search_hybrid 会把「标题 / 正文关键词 / 语义」三种方法的结果各自归一化后加权相加。
    这里我们直接喂它三份固定结果，测的是合并逻辑本身，跟模型和数据库都无关。
    """
    def fake_search_files(keyword, db_path=store._DB_PATH):
        return [(1, "a.txt", "讲义A", "标题含「动态规划」")]

    def fake_search_keyword(query, top_k=5):
        return [
            ("讲义A", 0.5, "正文关键词匹配（TF-IDF 分数 0.5）"),
            ("讲义B", 0.25, "正文关键词匹配（TF-IDF 分数 0.25）"),
        ]

    def fake_search_semantic(query, top_k=5, min_score=0.3):
        return [("讲义A", 0.8, "语义检索：意思相近（相似度 0.8）")]

    monkeypatch.setattr(store, "search_files", fake_search_files)
    monkeypatch.setattr(search, "search_keyword", fake_search_keyword)
    monkeypatch.setattr(search, "search_semantic", fake_search_semantic)


def test_混合检索_被多个方法命中会列出多条原因(monkeypatch):
    _假装有三个来源(monkeypatch)

    results = search_hybrid("动态规划")

    # 讲义A 被三种方法都命中了：各自归一化后都是 1.0，等权相加 = 3.0
    assert results[0][0] == "讲义A"
    assert results[0][1] == 3.0
    assert results[0][2].count("；") == 2      # 三条原因，用「；」连起来

    # 讲义B 只被正文关键词命中：0.25 归一化后是 0.5
    assert results[1][0] == "讲义B"
    assert results[1][1] == 0.5


def test_混合检索_权重可以调(monkeypatch):
    _假装有三个来源(monkeypatch)

    # 只信语义：另外两种方法的权重设为 0
    results = search_hybrid("动态规划", w_title=0, w_keyword=0, w_semantic=1)

    # 讲义A 只剩语义那一分（归一化后 1.0 × 权重 1.0）
    assert results[0][0] == "讲义A"
    assert results[0][1] == 1.0
