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

**相关代码**：`studyorganizer/store.py` 里的 `search_files()`（`SELECT ... WHERE title LIKE ?`）

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

## 4. 导入慢：把重的库留到「用的时候」再 import

**遇到的问题**
- 跑 `pytest` 要 5 秒多，可测试本身几乎不耗时——全是些判断和比较，真正跑起来不到 1 秒。
- 怪的是：这些测试**根本没用语义模型**，那时间花在哪了？

**根本原因**
- 写在文件最顶上的 `import`，在这个模块**被导入的那一刻**就会执行。
- `sentence_transformers` 会连带把 `torch` 一起拉进来，那是个很大的库，光 import 就要好几秒。
- 测试文件开头写了 `from studyorganizer.search import ...`，于是光是这一行就付了这笔钱——
  哪怕测试压根不碰模型。

**解决方法（延迟导入）**
- 把它从文件顶部**移进真正用到它的那个函数里**：

```python
def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer   # 用到了才 import
        _model = SentenceTransformer(_MODEL_NAME)
    return _model
```

- 效果：测试从 **5.4 秒 → 1.5 秒**；`import studyorganizer.search` 之后 `torch` 也确实没被加载
  （可以用 `sys.modules` 验证：`'torch' in sys.modules` 是 `False`）。

**核心道理**
- **写在顶部的 `import` 是「不管用不用都要付的钱」；写进函数里是「用了才付」。**
- 判断标准：这个库是不是**又重、又不是每次都用**？是 → 就延迟导入。
- 不用担心会变慢：`import` 有缓存，第二次执行几乎零开销。
- 但别无脑用：轻量的库（`os`、`json`）放顶部更清楚。到处延迟导入会让人**看不出这个模块依赖什么**。

**相关代码**：`studyorganizer/search.py` 的 `_get_model()`（现已改名 `get_model()`）

## 5. 循环导入：让「建索引」和「检索」互相看得见，但只准单向依赖

**遇到的问题**
- 做向量持久化时，需要有个地方回答「库里哪些文件的向量过期了」。
- 直觉做法是写在 `search.py` 里（它本来就是管向量的），可算完向量要**存库**，
  那就得 `import store`；而 `store.py` 的 `import_folder` 又想导入完顺手建索引，
  于是要 `import search`——两边互相 import，转一圈回来了。

**根本原因**
- Python 导入一个模块时，会从头到尾执行它。A 执行到一半需要 B，
  就去执行 B；B 执行到一半又需要 A，可 A 还没执行完（里面那个名字还不存在），
  于是报 `ImportError: cannot import name ... (most likely due to a circular import)`。
- 根子上是**职责没分清**：`store` 只该管「怎么存」，不该管「什么时候该建索引」。

**解决方法（加第三个模块，把依赖捋成一条直线）**
- 新建 `studyorganizer/index.py`，专门放「建索引」这件事：

```
index.py  →  store.py    （读要算的、写算完的）
index.py  →  search.py   （借模型和模型名）

store.py  →  不 import index，也不 import search
search.py →  不 import index
```

- 关键点：**`index` 站上层，`store` 和 `search` 都待在下面。**
  底下的模块不认识上面的模块，箭头就永远转不回起点，循环自然断了。
- 为此把 `search.py` 的 `_get_model` / `_MODEL_NAME` 改成了公开的
  `get_model` / `MODEL_NAME`——`_` 开头是「本模块内部用」的意思，
  别的模块要用它，本来就该改成公开名字。

**核心道理**
- **两个模块互相 import，是「职责放错了」的信号，不是「import 写法不对」。**
  先别研究怎么让它编过，先问：这件事到底该谁管？
- 断循环的正经办法是**加一层**（谁依赖谁画成箭头，别绕圈），
  不是把 import 挪进函数里藏起来——那只是把错误推迟到运行时，更难查。
- 单向依赖还有个白送的好处：**谁也不能偷偷在建索引**。
  要建索引只能从 `index` 或界面层调，看一眼 import 就全知道了。

**相关代码**：`studyorganizer/index.py`（新建）、`studyorganizer/store.py` 的
`list_files_needing_embedding()` / `save_embedding()`、`studyorganizer/search.py` 的 `get_model()`
