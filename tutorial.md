# Python 小教程

> StudyOrganizer 项目前置语法，按学习顺序整理。只覆盖项目会用到的部分。
> 每课一个主题 + 一个小例子。后续新课程会继续追加到本文件末尾。

## 第一课：变量、字符串、print

```python
filename = "第一章 动态规划.txt"     # 变量 = 给值起名字
print(filename)                       # 显示到屏幕

course = "算法设计与分析"
print(course + " —— " + filename)     # + 拼接字符串

print(len(filename))                  # len 数字符串长度

filename = "第二章 背包问题.pdf"      # 变量可重新赋值
```

**要点**
- `=` 是"存进去"，不是"等于"。
- `"..."` 是字符串（文字）；不带引号的 `filename` 是"取出这个变量里的值"。
- `len(字符串)` 数长度。

## 第二课：列表和循环

```python
files = ["第一章 动态规划.txt", "第二章 背包问题.pdf", "作业1.docx"]

print(files[0])         # 第一个（下标从 0 开始！）
print(len(files))       # 列表长度

for f in files:         # 挨个拿出来
    print("找到：", f)

files.append("第三章 图论.pptx")   # 末尾追加
```

**要点**
- `[a, b, c]` 是列表。
- **下标从 0 开始**：`files[0]` 是第一个。
- `for x in 列表:` 冒号 + 缩进，逐项遍历。
- **缩进划分代码块**（4 个空格，别混 Tab），缩进错会报 `IndentationError`。

## 第三课：函数

```python
def greet(name):          # def 定义，name 是参数
    print("你好，" + name)

greet("小明")             # 调用

def count_chars(text):
    return len(text)      # return 把结果交出去

n = count_chars("第一章 动态规划.txt")
```

**要点**
- `def 名字(参数):` 定义，函数体要缩进。
- `print` 是"给人看"，`return` 是"给程序用"（要交结果给后面步骤，用 return）。
- 参数可有默认值：`def f(name, kind="未知")`。

## 第四课：读写文件

```python
with open("sample.txt", "r", encoding="utf-8") as f:
    text = f.read()          # 读全部 → 字符串

with open("sample.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()    # 读成列表，一行一个

with open("output.txt", "w", encoding="utf-8") as f:
    f.write("第一行\n")      # 写入（w 会清空原文件）
```

**要点**
- `open(路径, "r", encoding="utf-8")`：中文文件必须写 `encoding`。
- `with ... as f` 自动关文件，优先用。
- `\n` 是换行符；读到的行自带 `\n`，用 `line.strip()` 去掉。
- 报 `UnicodeDecodeError` 说明文件不是 UTF-8（Windows 记事本易存成 GBK）。
- 想看清中文输出，运行前加前缀：`PYTHONIOENCODING=utf-8 python test.py`。

## 第五课：条件判断 if

```python
score = 75
if score >= 90:
    grade = "优秀"
elif score >= 60:
    grade = "及格"
else:
    grade = "不及格"

if "动态规划" in filename:     # in 判断字符串是否包含
    print("相关")
```

**要点**
- `if / elif / else`：从上往下判断，命中一个就停。
- `in` 判断"在不在里面"；`or`/`and` 组合条件。
- **`=` 赋值，`==` 比较相等** —— 头号坑。

## 综合练习：扫描文件夹

```python
import os

def list_txt_files(folder):
    names = os.listdir(folder)
    result = []
    for name in names:
        if name.endswith(".txt"):
            result.append(name)
    return result

def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def main():
    folder = "practice"
    keyword = "动态规划"
    best_name = None
    best_count = 0
    for name in list_txt_files(folder):
        path = os.path.join(folder, name)
        text = read_text(path)
        count = text.count(keyword)     # 数关键词出现几次
        print(name, "→", count, "次")
        if count > best_count:          # 边遍历边找最大
            best_count = count
            best_name = name
    print("最多的是：", best_name, best_count, "次")

if __name__ == '__main__':
    main()
```

**要点**
- `os.listdir(folder)` 列出文件夹里所有名字。
- `os.path.join(folder, name)` 拼完整路径。
- `字符串.endswith(".txt")` 判断结尾。
- `文本.count(关键词)` 数出现次数。

## 第六课：字典 dict

```python
# 1. 空字典，花括号 {}
counts = {}
counts["讲义1.txt"] = 3     # 存：字典[键] = 值
counts["作业1.txt"] = 1
counts["笔记1.txt"] = 1

print(counts["讲义1.txt"])   # 取：得到 3

# 2. 一次创建（键: 值，逗号隔开）
scores = {"小明": 90, "小红": 85, "小刚": 78}

# 3. 遍历：.items() 同时拿键和值
for name, score in scores.items():
    print(name, "考了", score)

# 4. in 判断键是否存在
if "小红" in scores:
    print("小红在")

# 5. .get() 安全取值，没有就给默认值
print(scores.get("小强", 0))   # 没有"小强" → 0
```

**要点**
- 列表用数字下标 `files[0]`，字典用名字 `counts["讲义1.txt"]`。
- `字典[键] = 值` 存，`字典[键]` 取（键不存在直接取会报错）。
- `for 键, 值 in 字典.items():` 遍历。
- `键 in 字典` 判断有没有这个键；`字典.get(键, 默认值)` 安全取。

## 第七课：模块和包（import）

```python
# 模块 = 一个 .py 文件；包 = 一个文件夹 + __init__.py

from studyorganizer.extract import extract_text   # 从包里拿函数

text = extract_text("practice/讲义1.txt")
print(len(text))
```

**要点**
- 一个 `.py` 文件 = 模块（module），里面装函数。
- 一个文件夹 + `__init__.py` = 包（package），里面装模块。
- 类比：包 = 抽屉，模块 = 抽屉里的文件。
- `from 包.模块 import 函数`：把别的文件的函数拿来用。
- 好处：代码按职责分文件放，不堆在一个文件里。

## 第八课：常用字符串方法

```python
import os

os.path.basename("practice/名字.pdf")   # → "名字.pdf"（去掉路径）
os.path.splitext("名字.pdf")             # → ("名字", ".pdf")（拆出扩展名）

"abcabc".replace("b", "X")               # → "aXcaXc"（替换所有）

"a  b  c".split()                        # → ["a", "b", "c"]（按空格切）
"-".join(["a", "b", "c"])                # → "a-b-c"（用 - 拼起来）
```

**要点**
- `basename` / `splitext` 处理文件名路径。
- `replace(旧, 新)` 替换；`split()` 切成列表；`join(列表)` 拼成字符串。
- `" ".join(x.split())` 是经典"压掉多余空格"套路。

## 第九课：排序、切片、拉链、lambda、列表推导式

```python
# 1. range：生成 0 到 n-1 的一串数
for i in range(3):
    print(i)                       # 0 1 2

# 2. 切片：取列表的一部分
nums = [10, 20, 30, 40, 50]
nums[:2]                           # → [10, 20]（前 2 个）
nums[1:3]                          # → [20, 30]（下标 1 到 2）

# 3. zip：两个列表一一配对
list(zip(["a", "b"], [1, 2]))      # → [("a", 1), ("b", 2)]

# 4. sort + key：按指定标准排序
pairs = [("作业", 0.6), ("讲义", 0.8), ("笔记", 0.5)]
pairs.sort(key=lambda p: p[1], reverse=True)
# → [("讲义", 0.8), ("作业", 0.6), ("笔记", 0.5)]  按分数从高到低

# 5. round：四舍五入
round(3.14159, 2)                  # → 3.14

# 6. 列表推导式：一行的 for 循环
[x * 2 for x in [1, 2, 3]]         # → [2, 4, 6]
```

**要点**
- `range(n)`：0 到 n-1，常配合 `for i in range(len(列表))` 遍历下标。
- 切片 `列表[开始:结束]`：取一段；`[:k]` 是前 k 个。
- `zip(a, b)`：两个列表一一配对。
- `sort(key=函数, reverse=True)`：按 `key` 标准排序，`reverse=True` 是降序。
- `lambda 参数: 表达式`：`def` 的缩写，一次性小函数（`lambda p: p[1]` 即"取 p 的第 1 个元素"）。
- 列表推导式 `[表达式 for 变量 in 列表]`：一行生成新列表。

## 附：项目用到的第三方库

| 库 | 用途 | 导入 |
| --- | --- | --- |
| charset-normalizer | 自动检测文件编码（解决 GBK/UTF-8） | `from charset_normalizer import from_bytes` |
| pymupdf | 读取 PDF 文字（旧名 fitz） | `import pymupdf` |
| sentence-transformers | 文字变向量，做语义检索 | `from sentence_transformers import SentenceTransformer` |
| streamlit | 快速搭网页界面 | `import streamlit as st` |

> 详细用法见 `studyorganizer/` 各模块和 `NOTES.md`。
