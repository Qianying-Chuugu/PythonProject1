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

代价是**间距会变得说不准**（实测）：段落级的间距合成到文件级之后，有的被磨小
（「动态规划和贪心有什么区别」+0.243 → +0.110），有的几乎不变，
「0-1 背包问题的状态转移方程是什么」甚至**反过来变大**（-0.016 → +0.040）
——因为平均把那个偏高的噪音段拉下来了。原因是同一文件里"够格但没那么准"的段落
（刚过 0.45 的那些）会把最好的那段往下拉。

好处是排序没受影响（21 条查询的 top-1 全对），文件分也确实比单看一段更稳；
坏处是"正确答案和噪音差多少"这个余量不稳定，不能拿它当质量指标。
真到需要更大区分度的场景，可以考虑对段落分做非线性加权（比如只认接近最高分的
那几段），那是个独立的话题。

> **下面每个数字都来自 `tools/benchmark.py`，可以自己重跑。**
> `python tools/benchmark.py --model <模型名>`，语料 `practice/`（22 文件 141 段）。
> 「放行率」= 21 条标了标准答案的查询 × 全部段落里，相似度 ≥ 0.45 的比例（21×141=2961）；
> 放行得越少，说明阈值越在干活。「排第 1」= 标准答案在文件级结果里排第一的条数。
>
> | 模型 | 0.45 放行率 | 排第 1 | 编码 141 段 | 体积 | 维度 |
> | --- | --- | --- | --- | --- | --- |
> | `text2vec-base-chinese`（旧） | 1351/2961 = 46% | 15/21 | 4.9s | 390 MB | 768 |
> | **`bge-small-zh-v1.5`（现用）** | **677/2961 = 23%** | **21/21** | **1.2s** | **92 MB** | **512** |
> | `bge-base-zh-v1.5` | 219/2961 = 7% | 20/21 | 7.5s | 781 MB | 768 |
>
> 换模型的理由看「排第 1」那一列，不看放行率：旧模型 21 条里有 6 条答案不在第一，
> 其中「最大似然估计怎么估计参数」被排到**第 11 名**（那是张期末试卷，篇幅短、
> 又被一堆定义埋着）。bge-small 21 条全对，放行率同时从 46% 降到 23%。
> **bge-base 是"更大但没更准"的实证**：放行率能压到 7%，排序上却**反而更差**
> （20/21），栽在跟旧模型同一条查询上（Dijkstra / Floyd），还要 8 倍体积、6 倍耗时。
>
> **「21/21」里有水分，得说清楚。** 其中 Dijkstra / Floyd 那条，bge-small 只赢
> **+0.006**（0.535 vs 0.529），基本是掷硬币：这条查询对三个模型都骑在边界上，
> bge-small 是"刚好站住"，不是"稳稳拿住"——bge-base 在它上面就输 0.014。
> 所以别把 21/21 读成"检索不会有问题"。
>
> **换模型时刻意没有重调 0.45，也没打算靠调它提升效果——实测它不是"越高越严"的旋钮。**
> 21 条查询下：0.45~0.60 都是 21/21；调高到 0.65 崩到 17/21（四条查询的答案段落
> 被整条砍掉，直接"未上榜"）；**调低到 0.30 / 0.40 反而掉到 20/21**
> （「过拟合怎么解决」被顶到第 2）。原因是上一节那个合成规则：`min_score` 不只过滤，
> 它还决定"前 3 段平均"从哪些段里取——放宽会让更多"够格但没那么准"的段落参与平均，
> 把文件分拖下来，排序跟着变。**阈值同时是过滤器和评分口径的一部分。**
>
> 局限要记清楚：**绝对阈值分不干净，而且比"区间重叠"更糟。**
> 「0-1 背包的状态转移方程」这条，**不相关段落里最高的那个比答案里最高的还高**
> （bge-small：0.766 vs 0.750，间距 -0.016；旧模型 -0.073）。它最后仍能排第 1，
> 靠的是"前 3 段平均"，不是阈值。真正决定顺序的是排序，不是阈值。
> 要彻底解决得靠更强的模型，或者改成「相对阈值」（只留每个文件里明显高于全库平均的那些段）。
>
> 还有一条要警惕：**这 21 条查询是手工挑的，`practice/` 里又有 5 个文件都在讲动态规划**
> （见 NOTES.md 第 8 条）。所以「21/21」只等于"这几条上没问题"，**不等于"检索没问题"**。
> 覆盖面：22 个文件里 21 个至少当过一条查询的答案；唯一没标的是 `作业1.txt`，
> 它按设计就是个"经常排得高、却从来不是答案"的干扰项（「背包」那条它排第 2）。

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

### 读向量时也要核对 embedding_model
`store.list_file_vectors(model_name)` / `list_chunk_vectors(model_name)` 都带
`AND embedding_model IS ?`，只返回**当前模型**算的向量。

为什么读的时候也要查这一列（而不只是写的时候标记过期）：不同模型的向量维度可能不一样
（text2vec 768 维、bge-small 512 维）。库里真会出现两种并存的情况——换模型要把全库
重算一遍，几十秒的事，用户等不及 Ctrl-C 就中断了。混着读出来，`np.vstack` 或
`cosine_similarity` 会直接崩：

```
ValueError: Incompatible dimension for X and Y matrices: X.shape[1] == 512 while Y.shape[1] == 768
```

加上过滤之后，这种半成品状态**不再是崩溃，只是"暂时读不到"**：`search_semantic`
返回空列表，聚类照常（文档向量那一半已经重算完了）。补跑一次 `ensure_*` 就恢复正常
——实测过：中断后 `search_semantic` 返回 0 条、`cluster_files` 分出 15 组不崩，
补跑 `ensure_chunk_embeddings()` 后检索结果和之前完全一致。

口径和 `list_*_needing_embedding(model_name, ...)` 是**同一个**：两边都只认
「这行的模型名 == 当前模型名」。写和读用同一个判断，不会出现「写的时候作废了、
读的时候又当成有效」的错位。

>`model_name` 定为必填参数（不是默认 `None`），而且顺着
>`search → store`、`plan → cluster → store` 一路透传，
>`app.py` 传 `search.MODEL_NAME`。这样"忘了传"会当场报错，而不是悄悄退化成
>不过滤。`index` 早就是这么做的，现在读的路径跟它对齐了。

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

**实测数字也必须可复现。** 本文里所有检索质量相关的数（放行率、间距、模型对照表）
都出自 `tools/benchmark.py`，不是一次性脚本跑出来的：

```
python tools/benchmark.py                                  # 测当前模型
python tools/benchmark.py --check                          # 回归检查（可卡 CI / 卡手工步骤）
python tools/benchmark.py --model BAAI/bge-base-zh-v1.5     # 换模型对比
```

它做三件事：① 走真正的生产路径建库（`index.import_and_index`）；② 每条测试查询调
**真的** `search.search_semantic()`，看标准答案排第几；③ 再做段落级间距和阈值扫描。

**加 `--check` 才判定，不加只报告。** 加上之后，只要有一条查询的标准答案没排在
第一位，就以非 0 退出。这是这个工具真正的用处所在——「报告好看」没有意义，
要能**挡住"改检索改坏了"**。所以改完 `search.py` / `chunk.py` / 换模型，跑一次
`--check` 那行。失败时它会同时列出两种可能（检索真的退化了 / 标准答案标错了），
而不是让你直接去改检索代码——NOTES.md 第 8 条就是这么栽的。

三个要注意的地方：

- **标准答案写在脚本里的 `QUERIES` 里，每条都注明依据。** 标之前必须打开文件读
  ——NOTES.md 第 8 条记着凭文件名猜答案、差点得出「模型分不清」错误结论的教训。
- 它用一个**临时数据库**（把工作目录切到临时目录，`store._DB_PATH` 是相对路径，
  默认参数自然就落在那儿了），**绝不碰仓库里的 `studyorganizer.db`**；
  跑完还会核对那个文件的指纹，被改动就报错。
- 比对之前会把**文件名翻译成库里的标题**（`extract` 会清洗文件名，NOTES.md 第 10 条）。
  标准答案文件名在语料里找不到、或者两条查询重复，脚本会当场停下。

局限：这 21 条查询是手工挑的，语料也只有 22 个文件。所以它是**回归参照**，
不是权威评测集——「21/21」只说明这几条上没问题。

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
