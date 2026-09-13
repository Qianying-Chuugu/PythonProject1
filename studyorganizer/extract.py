"""extract 模块：把文件里的文字读出来。

这是 StudyOrganizer 的第一个模块，负责"文本提取"。
支持 .txt / .md / .pdf，能识别扫描件（无文字层的 PDF）。
"""

import os
from charset_normalizer import from_bytes
import pymupdf

# 文件名里常见的"噪音词"，提取标题时要删掉
_NOISE_WORDS = ["最终版", "副本", "修订版", "定稿", "最新版", "初稿"]


def _read_plain_text(path):
    """读出一个纯文本文件的全部文字，自动检测编码（.txt 和 .md 都走这里）。"""
    with open(path, "rb") as f:          # rb：按二进制读，拿到原始字节
        raw = f.read()
    match = from_bytes(raw).best()       # 自动检测编码
    return str(match)                    # 用检测到的编码解码成文字


def _read_pdf(path):
    """读出一个 PDF 的全部文字。"""
    doc = pymupdf.open(path)             # 打开 PDF
    pages = []
    for page in doc:                     # 逐页
        pages.append(page.get_text())    # 取这一页的文字
    doc.close()
    return "\n".join(pages)              # 各页之间用换行连起来


def extract_text(path):
    """
    读出一个文件的全部文字，根据扩展名选择读法
    参数 path：文件路径
    返回：文件里的全部文字（字符串）
    """
    if path.endswith(".pdf"):
        return _read_pdf(path)
    else:
        # .txt / .md 目前都是纯文本，读法一样
        return _read_plain_text(path)


def extract_title(path):
    """
    从文件路径提取一个干净的标题。
    例：practice/动态规划_最终版.pdf → 动态规划
    """
    name = os.path.basename(path)           # 只要文件名部分
    name = os.path.splitext(name)[0]        # 去掉扩展名

    for noise in _NOISE_WORDS:              # 逐个去掉噪音词
        name = name.replace(noise, "")

    name = name.replace("_", " ").replace("-", " ")  # 分隔符统一成空格
    return " ".join(name.split())           # 压掉多余空格、去头尾


def is_scanned_pdf(path):
    """判断一个 PDF 是不是扫描件（没有文字层）。"""
    return _read_pdf(path).strip() == ""   # 文字为空 → 很可能是扫描件


def extract_file(path):
    """
    提取一个文件的全部信息，返回字典
    字典包含：path 文件路径、title 标题、text 正文全文
    如果是 PDF，还会多一项 is_scanned（是否扫描件）
    """
    info = {
        "path": path,
        "title": extract_title(path),
        "text": extract_text(path),
    }
    if path.endswith(".pdf"):
        info["is_scanned"] = is_scanned_pdf(path)
    return info
