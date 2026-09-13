# StudyOrganizer

AI 课程资料整理与语义检索系统。

## 解决什么问题

大学生电脑里堆着大量命名混乱的讲义、试卷、作业、实验报告和笔记，
难以分类和查找。StudyOrganizer 把杂乱的资料文件夹导入后，
自动完成文本提取、分类打标签、聚类和语义检索，
并生成一份可供用户确认的整理方案。

## 核心特点

普通文件管理器主要依靠目录和文件名。StudyOrganizer 同时比较三种检索方法：

1. 文件名关键词匹配
2. 正文关键词检索（TF-IDF / BM25）
3. 基于文本向量的语义检索（Sentence Transformers）

检索结果不仅返回相关文件，还会**解释为什么匹配**（哪个方法命中、命中了哪些内容）。

## 核心流程

```
导入资料 → 提取文本 → 判断资料类型 + 猜课程 → 存库
        → 关键词/语义检索 → 聚类 → 生成整理方案 → 用户确认
```

## 第一版功能

- 支持 PDF、TXT、Markdown 文件
- 自动提取标题、正文和文件信息
- 自动判断资料类型：讲义 / 作业 / 试卷 / 笔记 / 实验报告
- 自动推测课程归属（半自动：从文件名猜课程，用户在界面确认 / 修改）
- 三种检索：文件名关键词 / 正文关键词（TF-IDF）/ 语义（Sentence Transformers），并按权重混合
- 检索结果给出「匹配原因」，解释为什么命中（哪种方法、分数多少）
- 内容相近的文件自动聚类
- 生成整理方案（归并建议），用户确认后可导出报告
- SQLite 持久化
- Streamlit 界面
- **只读导入 + 建议方案**：不自动移动/删除原文件，用户确认后再操作

## 技术栈

| 层 | 选型 |
| --- | --- |
| 界面 | Streamlit |
| 存储 | SQLite |
| PDF 提取 | PyMuPDF |
| 关键词 / 分类 / 聚类 | scikit-learn |
| 语义向量 | Sentence Transformers（中文小模型，CPU 可跑） |
| 测试 | pytest |
| 接口（第二阶段） | FastAPI |

## 项目结构

```
studyorganizer/
├── extract.py    # 文本提取：txt/md/pdf、标题清洗、扫描件判断
├── classify.py   # 规则分类：讲义/作业/试卷/笔记/实验报告
├── course.py     # 从文件名猜课程归属（半自动，规则打底）
├── store.py      # SQLite 存储：建表/存文件/批量导入/查询/整理方案/课程
├── search.py     # 三种检索（关键词 / TF-IDF / 语义）+ 混合检索
├── cluster.py    # 层次聚类：把内容相近的文件归组
└── plan.py       # 整理方案：生成归并建议、确认、导出报告
```

## 运行方式

### 用界面（推荐）

```bash
pip install -r requirements.txt
streamlit run app.py
```

浏览器会自动打开，可以导入文件夹、浏览文件、搜索、生成并确认整理方案。

### 只用核心库（命令行）

```python
from studyorganizer import store
store.init_db()
store.import_folder("你的资料文件夹")   # 自动「提取 → 分类 → 存库」
store.search_files("动态规划")          # 按标题关键词搜
```

## 文档导航

- [DESIGN.md](DESIGN.md) —— 架构、数据流与重要设计
- [DECISIONS.md](DECISIONS.md) —— 技术选择及理由
- [ROADMAP.md](ROADMAP.md) —— 阶段目标与任务进度
- [CHANGELOG.md](CHANGELOG.md) —— 版本变更
