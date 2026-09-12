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

## 2. 单元素元组要加逗号（sqlite 报 "Incorrect number of bindings"）

**遇到的问题**
- 用 sqlite3 执行带 `?` 占位符的 SQL 时，报错：
  `sqlite3.ProgrammingError: Incorrect number of bindings supplied. The current statement uses 1, and there are 4 supplied.`

**根本原因**
- 写的是 `(f"%{keyword}%")`，括号里只有一个元素且没加逗号，Python 直接把它当成字符串本身，而不是元组。
- sqlite3 拿到字符串 `"%讲义%"`，把它当成 4 个字符（`%`、`讲`、`义`、`%`），于是「1 个占位符对上了 4 个值」。

**解决方法**
- 单元素元组必须加逗号：`(f"%{keyword}%",)`。

**核心道理**
- `(x)` 就是 `x`，`(x,)` 才是元组。括号里只有一个元素时，**逗号决定它是不是元组**。

**相关代码**：`test.py` 里的 `search_files()`（`SELECT ... WHERE title LIKE ?`）

## 3. 持久数据 vs 会话状态（网页一进去就显示旧方案）

**遇到的问题**
- 网页打开时，整理方案区自动显示了旧的建议清单，但用户还没点"生成"。

**根本原因**
- `plan_items` 存在数据库里，是"持久"的，之前测试留下的数据被读出来了。
- 数据库的数据程序关了还在；普通变量每次重跑/重启会被重置。

**解决方法**
- 用 `st.session_state` 记住"本会话是否点过生成"，点过才显示。
- `st.session_state.get("show_plan")` 安全取值（键不存在时返回 None，不报错）。

**核心道理**
- 数据库 = 持久，跨会话都在；变量 = 临时，重跑就没了。
- Streamlit 每次交互都重跑脚本，普通变量会丢，`st.session_state` 能跨重跑保留。

**相关代码**：`app.py` 的整理方案部分
