"""extract 模块：把文件里的文字读出来。

这是 StudyOrganizer 的第一个模块，负责"文本提取"。
目前支持 .txt 和 .md，以后 PDF 会在这里加。
"""

from charset_normalizer import from_bytes


def _read_plain_text(path):
    """读出一个纯文本文件的全部文字，自动检测编码（.txt 和 .md 都走这里）。"""
    with open(path, "rb") as f:          # rb：按二进制读，拿到原始字节
        raw = f.read()
    match = from_bytes(raw).best()       # 自动检测编码
    return str(match)                    # 用检测到的编码解码成文字


def extract_text(path):
    """读出一个文件的全部文字，根据扩展名选择读法。

    参数 path：文件路径
    返回：文件里的全部文字（字符串）
    """
    if path.endswith(".md"):
        return _read_plain_text(path)
    else:
        # .txt 以及其他暂时按纯文本处理
        return _read_plain_text(path)
