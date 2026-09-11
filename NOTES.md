# 开发笔记

> 记录我在开发 StudyOrganizer 过程中的经验、踩过的坑和解决方法。
> 每解决一个难题，就在末尾追加一条。

## 1. 读文本时编码不统一（UnicodeDecodeError）

**遇到的问题**
- 不同文件编码不一样：有的存成 UTF-8，有的存成 GBK。
- 之前写死 `encoding="utf-8"`，一遇到 GBK 文件就报错崩溃：
  `UnicodeDecodeError: 'utf-8' codec can't decode byte ...`

**根本原因**
- 文件在硬盘上存的是一串字节（0101），不是文字。
- 要把字节变回文字，必须先知道它当初是用什么编码写的。

**解决方法（三步）**
1. 用 `rb` 二进制模式读，先拿到原始字节（`b` = binary，别急着翻译）；
2. 用 `charset_normalizer.from_bytes(原始字节)` 自动检测编码；
3. 按检测到的编码把字节解码成文字。

**核心道理**
- 不告诉程序文件是什么编码，它只能瞎猜，猜错就崩溃。
- 所以顺序是「先读字节 → 自动检测 → 再解码」。

**相关代码**：`studyorganizer/extract.py` 里的 `_read_plain_text()`
