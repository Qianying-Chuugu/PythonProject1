# DESIGN —— 架构、数据流与重要设计

## 分层原则：核心逻辑与界面彻底分离

核心能力是纯 Python 包，Streamlit 只是薄壳。核心包是纯函数 + 依赖注入，
不依赖 `st.session_state`、文件对话框等 UI 细节。
这样第二阶段把核心封装成 FastAPI 接口时可以直接复用。

```
app.py            # Streamlit 入口（薄，只做展示与交互）
  └── 调用 ↓
studyorganizer/   # 核心包（纯逻辑，可独立测试）
  extract/ chunk/ classify/ course/ store/ search/ cluster/ plan/ index/
```

## 模块划分

| 模块 | 职责 |
| --- | --- |
| extract | 文本 / 标题 / 元信息提取（pdf / txt / md） |
| chunk | 把正文切成一段一段（自然段 + 超长段二次切）；纯函数 |
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
  → index     ① 文档向量 → files.embedding（聚类用）
              ② 切段 chunk.chunk_text() → chunks 表
              ③ 段落向量 → chunks.embedding（检索用）
              （向量很贵，所以算一次存起来，过期才重算）

检索：
  自然语言 query
  → search    三种方法：标题关键词 / 正文关键词（TF-IDF）/ 语义向量
              语义那一路是**按段落**比：每段算相似度 → 丢掉低于 min_score 的
              → 按文件分组，取最好的前 3 段平均当文件分
              三种方法各自归一化后加权 → 混合检索，结果附带「匹配原因」
              （向量从库里读，不现算）

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
- **文档级向量** → `files.embedding`，聚类用（判断「这些资料是否主题相近」）。
- **段落级向量** → `chunks.embedding`，语义检索用（判断「这段话回答了用户问什么」），
  命中后映射回文件。
- 原因：长文档整篇压成一个向量会把细节"平均"掉——一篇 30 页的讲义里只有一段讲了
  背包问题，整篇的向量跟"背包问题"并不像，整篇算就搜不到。

两种向量**分开算、各管各的**。不用「段落向量的平均值」代替文档向量，因为那样
聚类结果就会随切段参数变化（改个切段长度，聚类就变了），把两件无关的事耦合在一起。

### 切段：先按自然段，太长的再按字数切
`chunk.chunk_text()`，两层：

1. **按空行切自然段。** 注意单个换行**不算**分段——原文里一个换行往往只是
   "一行排不下"的显示折行（PDF 更是每一视觉行一个换行），所以段内的单换行要拼回去，
   否则会从句子中间切断，命中片段读起来是半截话。
2. **某段超过 300 字，再按字数滑窗切**，相邻块重叠 50 字（免得答案正好压在切口上）。

第 2 步**主要是给 PDF 准备的**。实测（`practice/操作系统_进程调度长讲义.pdf`）：
PDF 提取出来"空行只出现在页与页之间"，所以一"段"其实是一整页（380~410 字），
不二次切就等于没切。

### 检索结果怎么从段落合成到文件
结果列表里显示的还是**文件**（用户要打开的是文件，不是某个段落），所以要合成：

1. 先丢掉相似度低于 `min_score` 的段落；
2. 再按文件分组，取该文件**最好的前 3 段求平均**。

取平均而不是取最高分：既奖励"有一段特别准"，也奖励"好几段都相关"，而且不像取最高分
那样偏向段落多的长文档（段落多，蒙中高分的机会就多）。

代价是**间距会被平均掉一部分**（实测）：段落级的正确答案 vs 不相关是 +0.11 ~ +0.13，
合成到文件级只剩 +0.05 ~ +0.07。原因是同一文件里"够格但没那么准"的段落（刚过 0.45
的那些）会把最好的那段往下拉。所以排序没变（三条查询的 top-1 都仍然正确），
但"正确答案和噪音差多少"这个余量变小了。真到需要更大区分度的场景，
可以考虑对段落分做非线性加权（比如只认接近最高分的那几段），那是个独立的话题。

> **`min_score` 默认 0.45 是实测出来的，不是拍脑袋定的。** 在 `practice/` 语料
> （22 文件 141 段）上量过。核心指标是「卡同一个阈值，放行多少段落」——放行得越少，
> 说明阈值越在干活：
>
> | 模型 | 0.45 的放行率 | 正确答案 vs 不相关（间距） | 编码 141 段 | 体积 |
> | --- | --- | --- | --- | --- |
> | `text2vec-base-chinese`（旧） | 74% | +0.085 / +0.028 / +0.060 | 4.5s | 391M |
> | **`bge-small-zh-v1.5`（现用）** | **31%** | **+0.133 / +0.096 / +0.110** | **1.1s** | **92M** |
> | `bge-base-zh-v1.5` | 19% | +0.172 / +0.093 / +0.113 | 6.9s | 781M |
>
> 旧模型会放行 74% 的段落 = 阈值形同虚设；bge-small 只放行 31%，第一次真正在过滤。
> bge-base 间距只略好一点，却要 8 倍体积和 6 倍耗时，不划算。
>
> **换模型时刻意没有重调这个数。** 实测三条干净查询的交集大约在 0.66，能让这三条全对，
> 但那是对 3 个查询过拟合出来的数字，换批资料就翻车。0.45 的定位始终只是
> 「砍掉明显跑题的尾部」。
>
> 局限要记清楚：**绝对阈值分不干净**。时间片那条的相关段落最低 0.566，而背包那条
> 的不相关段落最高 0.653，两个区间是**重叠**的——没有任何一个数能同时满足。
> 真正决定顺序的是排序，不是阈值。要彻底解决得靠更强的模型，或者改成「相对阈值」
> （只留每个文件里明显高于全库平均的那些段）。

### 向量只算一遍：算完存库，过期才重算
向量算一次要过模型，很贵。所以算完就写进库里，检索和聚类都从库里读，不现算。

`files` 和 `chunks` 两张表的结构是对称的（都有 `embedding` + `embedding_model`），
过期规则也完全一样，收敛成同一条查询：

1. `embedding IS NULL` —— 还没算过，或者正文变了被清空；
2. `embedding_model` 和当前模型名对不上 —— 换模型了，旧向量不在同一个空间里，比对没有意义；
3. 文件正文变了 —— `save_file` 的 upsert 里用
   `CASE WHEN files.text IS excluded.text THEN files.embedding ELSE NULL END`
   把向量清成 NULL，等于插一面「这行过期了」的旗子；段落那边则是把这文件的
   chunks **整批删掉**，下次重新切、重新算。

这样「换模型」不用写任何特殊代码：所有行都不满足条件，自然全部重算。
「换个切段长度重来」也不用写迁移，删掉重导即可。

依赖方向：`index → store, search, chunk`。store / search / chunk 都**不**依赖 index，
所以建索引只能从 `index` 或界面层触发，`search` 内部不能反过来调它（会循环导入）。
`chunk` 更是谁的依赖都不欠——纯字符串进、纯列表出。

### 一个已知的隐患：换模型换到一半被打断
`store.list_file_vectors()` / `list_chunk_vectors()` 只查 `embedding IS NOT NULL`，
**不核对 `embedding_model`**。正常路径上没问题——`app.py` 启动时先跑完 `ensure_*`
才会渲染出搜索框，所以检索时库里的向量必然是同一个模型。

但如果重算中途被中断（重算是几十秒的事，用户等不及 Ctrl-C 很正常），库里就会
一半旧模型（768 维）、一半新模型（512 维）。这时 `np.vstack` 或
`cosine_similarity` 会直接崩：
`ValueError: Incompatible dimension for X and Y matrices: X.shape[1] == 512 while Y.shape[1] == 768`。

不是静默出错（会响），而且**下次启动会自动重算补上**，所以是个自愈的小坑。
但报错信息对新手不友好。要根治就让这两个读函数也按 `embedding_model` 过滤
（口径和 `list_*_needing_embedding` 一致）。

### 一个已知的接口不整齐处
`store` 的函数都收 `db_path` 参数，但 `search` / `cluster` / `plan` 的函数不收，
它们固定用 `store._DB_PATH`（相对的 `studyorganizer.db`）。
所以想对「另一个库」做检索，只能换工作目录，不能传参。
测试里是靠 monkeypatch 掉 `store` 的读取函数绕过去的。以后要在界面上支持多库，
得先把 `db_path` 一路透传下去。

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

> 注意：下面是**完整设计草案**。v0.1 已实现 `files` / `plan_items` / `courses` / `chunks`
> 四张表（`files` 已加 `suggested_course_id` / `course_id`，见 D-012，另有 `is_scanned` /
> `embedding` / `embedding_model`；`chunks` 见上文「切段」一节），
> 其余（tags / file_tags）是后续设计，尚未实现。
>
> `chunks.file_id` 实际**没有**建外键约束，只记关系——和 `files.course_id` 的写法保持一致
> （SQLite 的外键默认不生效，要每次连接都 `PRAGMA foreign_keys=ON` 才管用）。
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
>
> 但要知道现在的做法是**每次检索都把全库段落向量读进内存**再算余弦。
> `practice/` 22 个文件切出 141 段，跑起来是毫秒级，完全够用；
> 等到几万段、或者要在 Streamlit 每次重跑里做这件事，就该换向量索引了。
