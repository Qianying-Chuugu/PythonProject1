# DESIGN —— 架构、数据流与重要设计

## 分层原则：核心逻辑与界面彻底分离

核心能力是纯 Python 包，Streamlit 只是薄壳。核心包是纯函数 + 依赖注入，
不依赖 `st.session_state`、文件对话框等 UI 细节。
这样第二阶段把核心封装成 FastAPI 接口时可以直接复用。

```
app.py            # Streamlit 入口（薄，只做展示与交互）
  └── 调用 ↓
studyorganizer/   # 核心包（纯逻辑，可独立测试）
  extract/ classify/ course/ store/ search/ cluster/ plan/ index/
```

## 模块划分

| 模块 | 职责 |
| --- | --- |
| extract | 文本 / 标题 / 元信息提取（pdf / txt / md） |
| classify | 规则分类：判断资料类型 |
| course | 从文件名猜课程归属（半自动，规则打底） |
| store | SQLite 读写（files / courses / plan_items 三张表） |
| search | 三种检索（标题关键词 / 正文 TF-IDF / 语义向量）+ 混合检索 + 模型加载 |
| cluster | 层次聚类：内容相近的文件归组 |
| index | 建索引：把正文算成向量存进库里，并判断哪些行过期了要重算 |
| plan | 生成 / 确认 / 导出整理方案 |

## 数据流

```
导入文件
  → extract   提取标题/正文/元信息
  → classify  判断资料类型
  → store     存入 files 表
  → index     把正文算成向量写进 files.embedding（很贵，所以算一次存起来）

检索：
  自然语言 query
  → search    三种方法：标题关键词 / 正文关键词（TF-IDF）/ 语义向量
              各自归一化后加权 → 混合检索，结果附带「匹配原因」
              （语义向量从库里读，不现算）

聚类与整理：
  → cluster   内容相近的文件归组
  → plan      生成归并建议 → 用户确认 → 导出报告
```

## 核心抽象：统一接口

> 注意：以下「统一接口」目前**尚未实现**，是后续设计。
> v0.1 用的是简单函数（classify_type / search_semantic / cluster_files），
> 还没抽象成接口。留待 v0.2 或后续重构。

三个地方计划抽象成「统一接口 + 多实现」，便于替换与扩展：

```python
# 1. 类型分类器（v1 规则打底，后续 ML 作为第二个实现）
class TypeClassifier(Protocol):
    def classify(self, file) -> DocTypePrediction: ...

# 2. 课程候选建议（半自动）
class CourseSuggester(Protocol):
    def suggest(self, file) -> list[CourseSuggestion]: ...

# 3. 检索器（三种方法天然是三个实现）
class Retriever(Protocol):
    def search(self, query: str, k: int) -> list[Hit]: ...

@dataclass
class Hit:
    file_id: int
    score: float
    reasons: list[Reason]   # 为什么匹配：方法 + 命中内容 + 片段
```

## 重要设计

### 向量分块：两种粒度、两种用途
- **文档级向量** → 聚类（判断「这些资料是否主题相近」），目前语义检索也用它。
- **段落级向量** → 语义搜索（判断「这段话回答了用户问什么」），命中后映射回文件。**尚未实现**。
- 原因：长文档整篇压成一个向量会稀释语义、检索不准。

### 向量只算一遍：算完存库，过期才重算
文档级向量算一次要过模型，很贵。所以算完就写进 `files.embedding`，
`search_semantic` 和 `cluster_files` 都从库里读，不现算。

「哪些行的向量已经不算数了」收敛成同一条查询（`store.list_files_needing_embedding`）：
1. `embedding IS NULL` —— 还没算过，或者正文变了被清空；
2. `embedding_model` 和当前模型名对不上 —— 换模型了，旧向量不在同一个空间里，比对没有意义；
3. 文件正文变了 —— `save_file` 的 upsert 里用
   `CASE WHEN files.text IS excluded.text THEN files.embedding ELSE NULL END`
   把向量清成 NULL，等于插一面「这行过期了」的旗子。

这样「换模型」不用写任何特殊代码：所有行都不满足条件，自然全部重算。

依赖方向：`index → store, search`。store 和 search 都**不**依赖 index，
所以建索引只能从 `index` 或界面层触发，`search` 内部不能反过来调它（会循环导入）。

### 检索的「匹配原因」（可解释性 = 项目灵魂）
每个结果附带 `reasons`，标明命中的方法、命中的内容与片段。
既是对用户的解释，也是调试检索质量的工具（哪个方法拉垮一目了然）。
综合分 = 文件名关键词 + 正文关键词 + 语义向量 的加权，权重可调。

### 半自动分类必须留痕（系统建议 vs 用户修正）
分类是半自动的，所以「系统判成什么」和「用户改成什么」都要留档，否则：
- 无法统计分类器准确率（没有建议值可比）；
- 用户一改，自动值就被覆盖丢失，D-006 说的「改标签沉淀为 ML 训练数据」就断了。

做法：`files` 表存 `suggested_*` 列保留系统建议，最终值单独存；标签用 `status` 标记
`active / rejected`，用户拒绝自动标签时改状态而非删除，保留「系统建议过什么」的记录。

### 安全：只读 + 方案 + 确认
导入阶段只读原文件，绝不移动/删除。整理动作以 `PlanItem` 形式生成，
`status = pending`，用户确认后才执行，避免误删、误分类。

### 可复现性
固定随机种子；向量模型下载后缓存到固定路径，首次联网、之后离线可用。

## 数据模型（SQLite 草案）

> 注意：下面是**完整设计草案**。v0.1 已实现 `files` / `plan_items` / `courses` 三张表
> （`files` 已加 `suggested_course_id` / `course_id`，见 D-012，另有 `is_scanned` /
> `embedding` / `embedding_model`），其余（tags / file_tags / chunks）是后续设计，尚未实现。
>
> **实际建表 SQL 以 `studyorganizer/store.py` 的 `init_db()` 为准。** 上面的 `files`
> 草案里，`filename` / `size_bytes` / `mtime` / `review_status` / `imported_at` /
> `suggested_doc_type` / `suggestion_confidence` 等列**尚未实现**，是后续设计。

```sql
-- 课程
CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 文件（只读导入，记录原始路径，不移动）
CREATE TABLE files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,          -- 原始绝对路径
    filename TEXT NOT NULL,
    title TEXT,                          -- 清洗后的标题
    course_id INTEGER REFERENCES courses(id),   -- 最终课程（用户确认后）
    doc_type TEXT,                       -- 最终类型 lecture/assignment/exam/note/lab_report
    suggested_course_id INTEGER REFERENCES courses(id),  -- 系统候选课程（保留，不覆盖）
    suggested_doc_type TEXT,             -- 系统类型建议（保留，不覆盖）
    suggestion_confidence REAL,          -- 建议置信度
    review_status TEXT NOT NULL DEFAULT 'pending',  -- pending/confirmed/corrected
    size_bytes INTEGER,
    mtime TEXT,
    text TEXT,                           -- 提取的正文全文
    embedding BLOB,                      -- 文档级向量（numpy float32 的裸字节；聚类与语义检索用）
    embedding_model TEXT,                -- 这行的向量是哪个模型算的；对不上就要重算
    imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 标签（多对多，source 区分自动/人工）
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE file_tags (
    file_id INTEGER NOT NULL REFERENCES files(id),
    tag_id  INTEGER NOT NULL REFERENCES tags(id),
    source TEXT NOT NULL,                -- 'auto' | 'user'
    confidence REAL,                     -- 自动标签置信度，人工添加为空
    status TEXT NOT NULL DEFAULT 'active',   -- active | rejected（拒绝的自动标签保留记录）
    PRIMARY KEY (file_id, tag_id)
);

-- 段落（语义检索用）
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(id),
    seq INTEGER NOT NULL,                -- 段落在文件内的顺序
    text TEXT NOT NULL,
    embedding BLOB,                      -- 段落级向量（numpy 序列化）
    UNIQUE (file_id, seq)
);

-- 整理方案（先建议、后确认、再执行）
CREATE TABLE plan_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,                -- 归并 等
    files TEXT NOT NULL,                 -- 建议归并的文件标题（顿号连接）
    reason TEXT,                         -- 为什么
    status TEXT NOT NULL DEFAULT 'pending'  -- pending/confirmed/rejected
);
```

> 注：段落向量存 SQLite BLOB 足以应对几百~几千文件规模（numpy 加载进内存做余弦）；
> 后续规模扩大可换 FAISS / 独立向量库，接口不变。
