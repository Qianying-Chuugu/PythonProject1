"""测 search 模块里不依赖真向量模型的部分。

注意：这些测试**都不会加载语义模型**（那要下载几百 MB，测试不该干这个）。
- search_keyword 只用到 TF-IDF；
- search_hybrid 的三个来源我们用假函数替掉，测的是「合并、归一化、加权」这套自己的逻辑；
- search_semantic 用一个「假模型」：它把查询固定编码成 [1, 0]，
  于是我们只要构造 [x, y] 这样的段落向量，就能精确控制它和查询的余弦相似度。
"""

import math

import numpy as np
import pytest

from studyorganizer import search, store
from studyorganizer.search import (
    _normalize,
    search_hybrid,
    search_keyword,
    search_semantic,
)


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


# ---------- search_semantic：按段落匹配，再合成文件分 ----------

class _假语义模型:
    """假的向量模型：把查询固定编码成 [1, 0]，好让相似度完全可控。

    这样构造段落向量 [s, √(1-s²)]，它和查询的余弦相似度就正好是 s。
    """

    def encode(self, texts):
        return np.array([[1.0, 0.0]], dtype=np.float32)


def _向量(相似度):
    """造一个和查询向量 [1, 0] 余弦相似度正好等于「相似度」的二维向量。"""
    return np.array(
        [相似度, math.sqrt(max(0.0, 1 - 相似度 ** 2))], dtype=np.float32
    ).tobytes()


def _假装库里有段落(monkeypatch, 段落):
    """把库里的段落换成写死的假数据。

    参数 段落：[(文件标题, 段号, 相似度), ...]
    """
    rows = [
        (i, 标题, 段号, f"第{段号}段的正文", _向量(相似度))
        for i, (标题, 段号, 相似度) in enumerate(段落, start=1)
    ]
    monkeypatch.setattr(store, "list_chunk_vectors", lambda db_path=store._DB_PATH: rows)
    monkeypatch.setattr(search, "get_model", lambda: _假语义模型())


def test_语义检索_库里没有段落向量就返回空(monkeypatch):
    monkeypatch.setattr(store, "list_chunk_vectors", lambda db_path=store._DB_PATH: [])

    # 库是空的就直接返回，连模型都不该加载
    assert search_semantic("任意问题") == []


def test_语义检索_低分段落先被丢掉_不拉低文件分(monkeypatch):
    # 讲义A：一段特别准（0.9），其余全是 0.1 的废话
    # 讲义B：三段的相似度都只有 0.6，但都还算相关
    _假装库里有段落(monkeypatch, [
        ("讲义A", 1, 0.9),
        ("讲义A", 2, 0.1),
        ("讲义A", 3, 0.1),
        ("讲义A", 4, 0.1),
        ("讲义B", 1, 0.6),
        ("讲义B", 2, 0.6),
        ("讲义B", 3, 0.6),
    ])

    results = search_semantic("任意问题")
    分数 = {标题: 分 for 标题, 分, _原因 in results}

    # 关键：0.1 的段落绝不能混进平均分。少了 min_score 这道过滤，
    # 讲义A 会变成 (0.9+0.1+0.1)/3 ≈ 0.37，反而输给讲义B 的 0.6——
    # 那篇真正含答案的文件就搜不到了。
    assert 分数["讲义A"] == pytest.approx(0.9, abs=1e-3)
    assert 分数["讲义B"] == pytest.approx(0.6, abs=1e-3)
    assert results[0][0] == "讲义A"


def test_语义检索_多段够格时取最好的三段平均(monkeypatch):
    _假装库里有段落(monkeypatch, [
        ("讲义A", 1, 0.9),
        ("讲义A", 2, 0.8),
        ("讲义A", 3, 0.7),
        ("讲义A", 4, 0.4),      # 第四好的，够格但不参与平均
    ])

    results = search_semantic("任意问题")

    assert results[0][1] == pytest.approx((0.9 + 0.8 + 0.7) / 3, abs=1e-3)
    assert "最好的 3 段平均" in results[0][2]     # 解释里要说清分数怎么来的
    assert "第 1 段" in results[0][2]             # 命中片段来自分数最高的那段


def test_语义检索_只有一段够格时文件分就是那一段的分(monkeypatch):
    _假装库里有段落(monkeypatch, [("讲义A", 1, 0.9), ("讲义A", 2, 0.1)])

    results = search_semantic("任意问题")

    assert results[0][1] == pytest.approx(0.9, abs=1e-3)   # 不能被 0.1 拉低
    assert "平均" not in results[0][2]                     # 只有一段，没什么好平均的


def test_语义检索_结果按文件分从高到低排_最多top_k个(monkeypatch):
    _假装库里有段落(monkeypatch, [("甲", 1, 0.9), ("乙", 1, 0.8), ("丙", 1, 0.7)])

    assert [r[0] for r in search_semantic("任意问题")] == ["甲", "乙", "丙"]
    assert [r[0] for r in search_semantic("任意问题", top_k=2)] == ["甲", "乙"]


def test_语义检索_min_score可以调(monkeypatch):
    _假装库里有段落(monkeypatch, [("讲义A", 1, 0.2)])

    assert search_semantic("任意问题") == []                       # 默认门槛 0.3，0.2 被丢掉
    assert len(search_semantic("任意问题", min_score=0.1)) == 1     # 门槛调低就留下来了
