"""测 chunk 模块：把正文切成一段一段。

全是纯函数——不用数据库、不用模型，直接喂字符串、直接断言结果，
所以这些测试跑起来几乎不花时间。
"""

import pytest

from studyorganizer.chunk import chunk_text


# ---------- 第一层：按空行切自然段 ----------

def test_空文本切出零段():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  \n") == []      # 全是空白，等于没有内容


def test_单个自然段就是一段():
    assert chunk_text("这是一段话。") == ["这是一段话。"]


def test_单换行不算分段_要拼回去():
    # 原文里一个换行往往只是"一行排不下"的显示折行，一句话被折成两行而已。
    # 按单换行切就会从句子中间切断，命中片段读起来是半截话。
    text = "第一句被折成两行，\n第二行接在这里。\n\n这是第二个自然段。"
    assert chunk_text(text) == [
        "第一句被折成两行，第二行接在这里。",
        "这是第二个自然段。",
    ]


def test_折行拼回时英文单词之间要补空格():
    # 中文可以直接拼，英文不行——"brown" 和 "fox" 粘起来就变成一个词了
    text = "the quick brown\nfox jumps\n\n中文\n折行"
    assert chunk_text(text) == ["the quick brown fox jumps", "中文折行"]


def test_折行留下的缩进会被去掉():
    text = "第一行\n    缩进的第二行。"
    assert chunk_text(text) == ["第一行缩进的第二行。"]


# ---------- 第二层：太长的段按字数二次切 ----------

def test_超长段二次切分_相邻两块重叠():
    # 0-9 循环的 800 字。步长 = 300 - 50 = 250，
    # 所以切成 [0:300]、[250:550]、[500:800] 三块
    text = "".join(str(i % 10) for i in range(800))
    chunks = chunk_text(text, max_len=300, overlap=50)

    assert chunks[0] == text[0:300]
    assert chunks[1] == text[250:550]      # 开头往回退了 50 字 → 和上一块重叠
    assert chunks[2] == text[500:800]
    # 重叠的意义：答案正好压在切口上时，两块里至少有一块能完整读到它
    for 前, 后 in zip(chunks, chunks[1:]):
        assert 前[-50:] == 后[:50]


def test_刚好等于上限时不切():
    assert len(chunk_text("啊" * 300, max_len=300, overlap=50)) == 1


def test_超过上限一个字就切成两块():
    chunks = chunk_text("啊" * 301, max_len=300, overlap=50)
    assert [len(c) for c in chunks] == [300, 51]


def test_短段原样保留_长段才切():
    text = "短的一段。\n\n" + "长" * 400
    chunks = chunk_text(text, max_len=300, overlap=50)

    assert chunks[0] == "短的一段。"               # 没超上限，原样留着
    assert [len(c) for c in chunks[1:]] == [300, 150]   # 超了的才切


def test_overlap不小于max_len会报错():
    # 步长会变成 0，start 永远不前进 → 死循环。宁可早点报错。
    with pytest.raises(ValueError):
        chunk_text("啊" * 100, max_len=50, overlap=50)
    with pytest.raises(ValueError):
        chunk_text("啊" * 100, max_len=50, overlap=80)
