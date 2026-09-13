"""chunk 模块：把一篇正文切成一段一段的。

为什么要切：长文档整篇压成一个向量，里面的细节会被"平均"掉。
一篇 20 页的讲义里可能只有一段讲了背包问题，整篇的向量跟"背包问题"并不像，
搜不到；切成段落、每段一个向量，才能精确命中讲那段话的地方。

切法分两层：
  1. 先按空行切自然段。注意：**单个换行不算分段**——原文里一个换行
     往往只是"显示折行"（一行排不下），一句话被折成两行而已。
     所以段内的单换行要拼回去，不然会从句子中间切断。
  2. 某一段还是太长（超过 max_len），再按字数滑窗切开。

第 2 步主要是给 PDF 准备的：PDF 提取出来"每一视觉行一个换行、段落之间没有空行"，
所以一"段"其实是一整页，几百上千字，不二次切就等于没切。

纯函数：不碰数据库，也不碰模型，所以单独就能测。
"""

import re

_MAX_LEN = 300      # 一段最多多少字，超了就二次切
_OVERLAP = 50       # 二次切时相邻两块重叠多少字


def _join_wrapped(lines):
    """把一个自然段里被换行折断的几行拼回成一整句。

    大多数字符直接拼上就行（中文："算法思想，" + "核心是把…"）。
    但如果断点两边都是英文字母/数字，中间得补个空格——
    英文单词之间必须有空格，不能像中文那样直接粘。
    """
    merged = ""
    for line in lines:
        line = line.strip()          # 去掉折行留下的缩进
        if not line:
            continue
        if (merged and merged[-1].isascii() and merged[-1].isalnum()
                and line[0].isascii() and line[0].isalnum()):
            merged += " "
        merged += line
    return merged


def _split_paragraphs(text):
    """按空行切成自然段，段内的单换行拼回去。返回字符串列表，空的丢掉。"""
    blocks = re.split(r"\n[ \t]*\n", text)          # 空行（允许中间夹空格）分隔
    paragraphs = [_join_wrapped(b.splitlines()) for b in blocks]
    return [p for p in paragraphs if p]


def _split_long(paragraph, max_len, overlap):
    """把一个太长的段按字数滑窗切开。

    步长 = max_len - overlap：相邻两块因此会重叠 overlap 个字，
    免得答案正好压在切口上被切成两半，两边都匹配不上。
    """
    step = max_len - overlap
    pieces = []
    start = 0
    while start < len(paragraph):
        pieces.append(paragraph[start:start + max_len])
        if start + max_len >= len(paragraph):
            break                       # 已经切到末尾了
        start += step
    return pieces


def chunk_text(text, max_len=_MAX_LEN, overlap=_OVERLAP):
    """把正文切成一段一段，返回字符串列表（顺序就是原文顺序）。

    参数 max_len：一段最多多少字（默认 300）。
    参数 overlap：二次切时相邻两块重叠多少字（默认 50）。
    """
    if overlap >= max_len:
        # step 会变成 0 或负数，start 永远不前进 → 死循环。宁可早点报错。
        raise ValueError("overlap 必须小于 max_len，否则切片不会前进，会死循环")

    chunks = []
    for paragraph in _split_paragraphs(text):
        if len(paragraph) <= max_len:
            chunks.append(paragraph)
        else:
            chunks.extend(_split_long(paragraph, max_len, overlap))
    return chunks
