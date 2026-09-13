# StudyOrganizer

[English](#english) · [中文](#中文)

> **这不是一个做完的项目——这是一个正在做的项目，每一步都留在仓库里。**
>
> StudyOrganizer 是一个课程资料整理与语义检索工具。我一边学 Python，一边把它做出来：
> 教程从变量和 `print` 讲起，踩过的坑记在 [NOTES.md](NOTES.md)，
> 每个技术选择为什么这么定记在 [DECISIONS.md](DECISIONS.md)，做到哪了记在 [ROADMAP.md](ROADMAP.md)。
>
> 想要一个自己的项目、却不知道从哪下手？跟着这个仓库一起做就行。

![status](https://img.shields.io/badge/status-v0.1%20in%20progress-orange)
![license](https://img.shields.io/badge/license-MIT-blue)

<!-- 有截图后：把图片放到 docs/images/，改下面这行的链接即可（现在是占位图，不会显示成破图） -->
![界面截图](docs/images/screenshot.svg)

> 📷 *截图待补——你可以先 clone 下来自己跑一遍看看。*

---

## 中文

### 这是什么

一个**可以跟着做的真实 Python 项目**，不是玩具 demo。

它解决一个很具体的问题：大学生的电脑里堆着几百个命名混乱的讲义、试卷、作业、
实验报告和笔记，想找的时候翻半天。StudyOrganizer 把它们导入、自动分类，
然后你可以用自然语言去搜——**而且每个搜索结果都会告诉你它为什么匹配**，
不是甩给你一个看不懂的相似度分数。

它同时是一份教程。开发和写教程是同步进行的：学到什么、踩到什么坑，当场记下来。

### 目前做到哪了

**已完成**（v0.1 的核心闭环已经能跑通）：

- 导入 `.txt` / `.md` / `.pdf`，自动提取正文、清洗标题、识别扫描件
- 自动判断资料类型：讲义 / 作业 / 试卷 / 笔记 / 实验报告
- 从文件名猜课程归属（半自动，界面上确认或修改）
- **三种检索 + 混合检索**：文件名关键词 / 正文关键词（TF-IDF）/ 语义向量，结果带「匹配原因」
- **语义检索按段落比**：切段 → 每段存一个向量 → 命中后告诉你**是哪一段**、并把那一段贴出来
- 向量算一次就存进库里，正文变了或换了模型才重算（不会每次检索都现算）
- 内容相近的文件自动聚类 → 生成整理方案 → 用户确认 → 导出报告
- Streamlit 界面 + SQLite 持久化
- 向量模型是在示例语料上**实测选出来**的，不是拍脑袋：`BAAI/bge-small-zh-v1.5`
  （6 条查询里旧模型只有 4 条把答案排在第一，它 6 条全对；放行率 49% → 27%，
  体积和耗时都只有 1/4。对照数据在 [DESIGN.md](DESIGN.md)，
  **可以用 `python tools/benchmark.py --model 模型名` 自己重跑**）

**还没做**（正在做的，都在 [ROADMAP.md](ROADMAP.md) 里）：

- 改成**相对阈值**：现在的相似度下限是绝对分数线，实测分不干净——「0-1 背包的状态
  转移方程」这条，不相关段落里最高的那个（0.766）比答案里最高的（0.750）还高
- 统一接口抽象（`TypeClassifier` / `Retriever`，为将来换实现做准备）
- BM25、标签系统、文件重命名建议
- 真实模型的端到端检索测试没进默认测试集（要下载模型，跑起来太慢）——
  改成了手动跑 `tools/benchmark.py`，见 [DESIGN.md](DESIGN.md)「可复现性」

> ⚠️ **项目还在开发中**，接口和数据结构都可能变。现在跟上的话，你能看着它一点点长完。

### 新手怎么开始

**如果你是想学做项目的人，按这个顺序读：**

| 顺序 | 读什么 | 为什么 |
| --- | --- | --- |
| 1 | [`tutorial.md`](tutorial.md) | Python 语法，从变量和 `print` 讲起，只讲这个项目会用到的部分。有一个「扫描文件夹」的综合练习。**零基础从这里开始。** |
| 2 | [`studyorganizer/extract.py`](studyorganizer/extract.py) | 整个项目里最简单的一个模块，79 行。看完你就知道一个模块长什么样了。 |
| 3 | [`NOTES.md`](NOTES.md) | 我踩过的坑。**写代码报错的时候，先来这儿查。** |
| 4 | [`DECISIONS.md`](DECISIONS.md) | 想知道「为什么要这么写」的时候读。每条都是「决策 → 理由」。 |
| 5 | 其余模块 | 按 `chunk → classify → course → store → index → search → cluster → plan` 的顺序，由浅入深。 |

**如果你只想把它跑起来用**，往下看「快速开始」。

### 快速开始

```bash
git clone https://github.com/Qianying-Chuugu/StudyOrganizer-Python.git
cd StudyOrganizer-Python

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
streamlit run app.py
```

浏览器会自动打开。在左侧「文件夹路径」里填一个装着资料的文件夹，点「导入」，
然后就能在下面各个搜索框里试了。

**⚠️ 国内网络注意两件事：**

1. **装依赖慢** —— 换清华镜像：
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

2. **首次运行会下载模型** —— 语义检索用的 `BAAI/bge-small-zh-v1.5`
   第一次运行时会从 HuggingFace 下载（约 90 MB）。国内直连通常下不动，先设镜像：
   ```bash
   # Windows (cmd)
   set HF_ENDPOINT=https://hf-mirror.com

   # PowerShell
   $env:HF_ENDPOINT="https://hf-mirror.com"

   # macOS / Linux
   export HF_ENDPOINT=https://hf-mirror.com
   ```
   下载一次之后会缓存到本地，以后离线也能用。

> 提示：如果你还没有资料可以试，仓库里的 `practice/` 就是一份现成的示例语料
> （20 篇短资料，外加一篇 4000 字的讲义和一份 5 页的 PDF，专门用来试长文档检索）。
> `app.py` 默认的路径就是它，clone 下来直接点「导入」即可。

### 检索结果长什么样

每个结果都会说明**为什么命中**；语义检索还会告诉你**命中在哪一段**，并把那一段贴出来。
下面是真实运行输出（`practice/` 语料，搜「怎么判断过拟合」）：

```
机器学习 梯度下降讲义          0.576
  原因：语义检索：第 4 段最相近（相似度 0.672）
        「过拟合与欠拟合：- 过拟合：模型在训练集上表现很好，但在测试集上表现差，
        泛化能力…」
        文件分 = 最好的 2 段平均（全文共 2 段相关）
```

混合检索把几路结果合成一个总分，命中的方法各自署名：

```
机器学习 梯度下降讲义          总分 2.0
  原因：正文关键词匹配（TF-IDF 分数 0.106）；语义检索：第 4 段最相近（相似度 0.672）
        「过拟合与欠拟合：- 过拟合：模型在训练集上表现很好，但在测试集上表现差…」
```

有了**段号 + 片段**，你不用打开文件就知道该不该点进去。这也是「用自然语言搜」
和「Ctrl+F」的区别：语义那一路不需要标题或正文里出现你问的那几个字。

> 上面是真实输出，但**分数在不同语料上不可比**——这里只用来说明格式，
> 以及「为什么每个结果都要带原因」。换一批资料，绝对分数会变。

### 几个设计上的取舍

| 决定 | 理由 |
| --- | --- |
| **只读导入，绝不自动移动/删除原文件** | 误删和误分类不可逆。整理动作先作为「建议」生成，用户确认后才执行 |
| **结果必须解释「为什么匹配」** | 既是对用户的交代，也是调试检索质量的手段——哪个方法拉胯一目了然 |
| **分类半自动，且系统建议和用户修正分开存** | 保留「系统判成什么」的记录，将来才能统计准确率、拿来训 ML（见 [DECISIONS.md](DECISIONS.md) D-012） |
| **核心逻辑与界面彻底分离** | 核心是纯 Python 包，Streamlit 只是薄壳，将来换成 FastAPI 接口可以直接复用 |
| **全部离线，不接付费大模型** | 中文小模型 CPU 就能跑，大学生笔记本扛得住 |

### 项目结构

```
StudyOrganizer-Python/
├── app.py                  # Streamlit 界面入口（薄壳，只做展示与交互）
├── studyorganizer/         # 核心包（纯逻辑，可独立测试）
│   ├── extract.py          #   文本提取：txt / md / pdf、标题清洗、扫描件识别
│   ├── chunk.py            #   把正文切成一段一段（自然段 + 超长段二次切）
│   ├── classify.py         #   规则分类：讲义 / 作业 / 试卷 / 笔记 / 实验报告
│   ├── course.py           #   从文件名猜课程归属（半自动）
│   ├── store.py            #   SQLite 存储：建表 / 存取 / 查询 / 整理方案
│   ├── index.py            #   建索引：算向量存库 + 判断哪些行过期要重算
│   ├── search.py           #   三种检索（标题关键词 / TF-IDF / 语义）+ 混合检索
│   ├── cluster.py          #   层次聚类：把内容相近的文件归组
│   └── plan.py             #   整理方案：生成 / 确认 / 导出报告
├── tools/
│   └── benchmark.py        #   检索实测脚本：标准答案排第几 / 阈值扫描（手动跑）
├── tests/                  # pytest 测试
├── tutorial.md             # Python 语法教程 ← 新手从这里开始
├── NOTES.md                # 开发笔记：踩过的坑
├── DESIGN.md               # 架构、数据流、数据模型
├── DECISIONS.md            # 每个技术选择「为什么这么定」
├── ROADMAP.md              # 版本规划与任务进度
├── CHANGELOG.md            # 版本变更记录
└── requirements.txt
```

### 技术栈

| 层 | 选型 |
| --- | --- |
| 界面 | Streamlit |
| 存储 | SQLite |
| PDF 提取 | PyMuPDF |
| 关键词 / 分类 / 聚类 | scikit-learn |
| 语义向量 | Sentence Transformers（中文小模型，CPU 可跑） |
| 测试 | pytest |

### 文档导航

| 文件 | 内容 |
| --- | --- |
| [tutorial.md](tutorial.md) | Python 语法教程（九课 + 综合练习）。**零基础从这里开始** |
| [NOTES.md](NOTES.md) | 开发中踩过的坑和解决方法 |
| [DESIGN.md](DESIGN.md) | 架构、数据流、数据模型 |
| [DECISIONS.md](DECISIONS.md) | 技术选择及理由（ADR 风格） |
| [ROADMAP.md](ROADMAP.md) | 阶段目标与任务进度 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更 |

### 许可证

[MIT](LICENSE) —— 随便用。

---

## English

### What this is

A **real Python project you can build along with** — not a toy demo.

It solves one concrete problem: students end up with hundreds of messily-named lecture
slides, past exams, assignments, lab reports and notes, and finding anything is a pain.
StudyOrganizer imports them, classifies them automatically, and lets you search in plain
language — and **every result tells you why it matched**, instead of handing you an
opaque similarity score.

It's also a tutorial. Development and writing happen together: whatever I learn or break
gets written down right away.

> 📖 **Note:** the tutorial and the in-depth docs (`NOTES` / `DESIGN` / `DECISIONS` /
> `ROADMAP`) are currently written in **Chinese only**. This README is bilingual; the
> rest of the repo isn't yet.

### Where it stands

**Done** (the v0.1 core loop runs end to end):

- Import `.txt` / `.md` / `.pdf`; extract text, clean up titles, detect scanned PDFs
- Classify document type: lecture / assignment / exam / note / lab report
- Guess the course from the filename (semi-automatic — you confirm in the UI)
- **Three retrievers + hybrid search**: filename keywords / full-text TF-IDF / semantic
  embeddings, with an explanation attached to every hit
- **Semantic search works at paragraph level**: text is split into chunks, each gets its
  own vector, and a hit tells you **which chunk** matched and shows you that chunk
- Embeddings are computed once and stored; they're only recomputed when the text changes
  or you switch models (not on every search)
- Cluster similar files → suggest a cleanup plan → you confirm → export a report
- Streamlit UI + SQLite storage
- The embedding model was **picked by measurement**, not by vibes: `BAAI/bge-small-zh-v1.5`
  (across 6 labeled queries the old model put the answer first only 4 times; this one gets
  all 6. Pass rate 49% → 27%, and it's a quarter of the size and a quarter of the time.
  Comparison table in [DESIGN.md](DESIGN.md) — **you can rerun it yourself with
  `python tools/benchmark.py --model <name>`**)

**Not done yet** (tracked in [ROADMAP.md](ROADMAP.md)):

- **A relative threshold**: today's cutoff is an absolute similarity score, and measurement
  shows it can't separate cleanly — for "what's the 0-1 knapsack transition equation", the
  best *wrong* paragraph scores higher than the best *correct* one (0.766 vs 0.750)
- Unified interfaces (`TypeClassifier` / `Retriever`) to make implementations swappable
- BM25, a tag system, rename suggestions
- Real-model end-to-end retrieval tests aren't in the default suite (they'd have to
  download the model, so they're too slow) — they're a manual run via `tools/benchmark.py`
  instead; see "Reproducibility" in [DESIGN.md](DESIGN.md)

> ⚠️ **Work in progress.** APIs and data structures will change. If you start now,
> you get to watch it grow.

### Where to start

**If you're here to learn, read in this order:**

| # | Read | Why |
| --- | --- | --- |
| 1 | [`tutorial.md`](tutorial.md) | Python syntax from variables and `print` up, covering only what this project needs. **Chinese only.** Start here if you're new. |
| 2 | [`studyorganizer/extract.py`](studyorganizer/extract.py) | The simplest module in the project, 79 lines. After this you know what a module looks like. |
| 3 | [`NOTES.md`](NOTES.md) | Pitfalls I hit. **Check here first when something breaks.** |
| 4 | [`DECISIONS.md`](DECISIONS.md) | Every design choice, as "decision → rationale". |
| 5 | The rest | In this order: `chunk → classify → course → store → index → search → cluster → plan`. |

**If you just want to run it**, see below.

### Quick start

```bash
git clone https://github.com/Qianying-Chuugu/StudyOrganizer-Python.git
cd StudyOrganizer-Python

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
streamlit run app.py
```

Your browser opens automatically. Point "文件夹路径" in the sidebar at a folder of
documents, hit 导入, and try the search boxes below.

**⚠️ Two things to know on a slow network (e.g. from mainland China):**

1. **Dependency install may crawl** — use a mirror:
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```
2. **The first run downloads a model** — semantic search uses
   `BAAI/bge-small-zh-v1.5`, fetched from HuggingFace on first use
   (about 90 MB). Set a mirror first if the direct connection stalls:
   ```bash
   export HF_ENDPOINT=https://hf-mirror.com   # macOS / Linux
   set HF_ENDPOINT=https://hf-mirror.com      # Windows (cmd)
   ```
   It's cached locally after the first download and works offline afterwards.

> Tip: if you don't have your own documents handy, the `practice/` folder in this repo
> is a ready-made sample corpus (20 short files, plus a 4000-character lecture note and
> a 5-page PDF, there specifically to exercise long-document search). That's the path
> `app.py` defaults to — clone, hit import, done.

### What a result looks like

Every hit explains **why** it matched; semantic search also tells you **which chunk**
matched, and shows you that chunk. This is a real run against the `practice/` corpus,
searching for 「怎么判断过拟合」 ("how do you tell overfitting"):

```
机器学习 梯度下降讲义          0.576
  原因：语义检索：第 4 段最相近（相似度 0.672）
        「过拟合与欠拟合：- 过拟合：模型在训练集上表现很好，但在测试集上表现差，
        泛化能力…」
        文件分 = 最好的 2 段平均（全文共 2 段相关）
```

Hybrid search merges the retrievers into one total score, crediting each one that hit:

```
机器学习 梯度下降讲义          总分 2.0
  原因：正文关键词匹配（TF-IDF 分数 0.106）；语义检索：第 4 段最相近（相似度 0.672）
        「过拟合与欠拟合：- 过拟合：模型在训练集上表现很好，但在测试集上表现差…」
```

With the **chunk number + snippet** you can tell whether a file is worth opening without
opening it. That's also the difference between searching in plain language and hitting
Ctrl+F: the semantic retriever doesn't need your query terms to appear in the title or
body at all.

> That's real output, but **scores aren't comparable across corpora** — it's here to show
> the format and why every result carries its reasons. Swap in your own files and the
> absolute numbers will move.

### Design trade-offs

| Decision | Why |
| --- | --- |
| **Read-only import — never move or delete your files** | Misdeletion is irreversible. Cleanup actions are proposed as suggestions and only executed after you confirm |
| **Every result must explain itself** | It's both an answer to the user and a tool for debugging retrieval quality — you can see at a glance which retriever is underperforming |
| **Semi-automatic classification, with system suggestions and user corrections stored separately** | Keeps a record of what the system guessed, so accuracy can be measured later and the data can train an ML model (see D-012) |
| **Core logic fully decoupled from the UI** | The core is a plain Python package; Streamlit is just a shell, so a future FastAPI layer can reuse it directly |
| **Fully offline, no paid LLM APIs** | A small Chinese model runs on CPU — a student laptop can handle it |

### Project layout

```
StudyOrganizer-Python/
├── app.py                  # Streamlit entry point (thin shell)
├── studyorganizer/         # Core package (pure logic, independently testable)
│   ├── extract.py          #   Text extraction: txt / md / pdf, title cleanup, scanned-PDF detection
│   ├── chunk.py            #   Split a document into chunks (paragraphs, then sliding window)
│   ├── classify.py         #   Rule-based classification: lecture / assignment / exam / note / lab report
│   ├── course.py           #   Guess course from filename (semi-automatic)
│   ├── store.py            #   SQLite: schema / save / query / plan items
│   ├── index.py            #   Build the index: embed text, detect stale rows that need re-embedding
│   ├── search.py           #   Three retrievers (filename / TF-IDF / semantic) + hybrid search
│   ├── cluster.py          #   Hierarchical clustering of similar files
│   └── plan.py             #   Cleanup plan: generate / confirm / export
├── tools/
│   └── benchmark.py        #   Retrieval benchmark: answer rank / threshold sweep (manual run)
├── tests/                  # pytest
├── tutorial.md             # Python tutorial ← start here if you're new
├── NOTES.md                # Dev notes: pitfalls hit along the way
├── DESIGN.md               # Architecture, data flow, data model
├── DECISIONS.md            # Technical choices and rationale
├── ROADMAP.md              # Version plan and task progress
├── CHANGELOG.md            # Changelog
└── requirements.txt
```

### Tech stack

| Layer | Choice |
| --- | --- |
| UI | Streamlit |
| Storage | SQLite |
| PDF extraction | PyMuPDF |
| Keywords / classification / clustering | scikit-learn |
| Semantic embeddings | Sentence Transformers (small Chinese model, CPU-friendly) |
| Testing | pytest |

### License

[MIT](LICENSE) — do whatever you want with it.
