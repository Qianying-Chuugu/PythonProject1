# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/) 格式，版本号遵循 [SemVer](https://semver.org/)。

## [Unreleased]

### Added
- 项目初始化：确定 StudyOrganizer 的目标与第一版范围。
- 建立项目文档：README、ROADMAP、DESIGN、DECISIONS、CHANGELOG。
- 明确第一版范围：本地离线、只读导入、不移动原文件、先出建议方案。
- 新增根目录 `.gitignore`（排除 `.venv/`、`.idea/`、模型缓存、SQLite 文件等）。
- 数据模型补充：`files.suggested_*` 与 `file_tags.confidence/status`，
  用于保留系统建议与用户修正（见 DECISIONS D-012）。
- 核心包骨架 `studyorganizer/` 与 `extract.py`（extract_text 支持 .txt / .md）
- 文本提取自动检测编码（charset-normalizer），解决 GBK/UTF-8 混用
- 新增 `tutorial.md`（Python 语法教程）、`NOTES.md`（开发笔记）、`requirements.txt`
- 新增 `search.py`：语义检索（sentence-transformers 中文模型）
- 新增 `cluster.py`：层次聚类，把内容相近的文件归组
- 新增 `plan.py`：生成 / 确认 / 导出整理方案
- 新增 `app.py`：Streamlit 界面（导入 / 浏览 / 搜索 / 整理方案）
- 新增 `tests/`：pytest 覆盖 extract / classify / store
- 检索结果带「匹配原因」：标题关键词 / 正文关键词 / 语义各自解释为什么命中
- 新增正文关键词检索（TF-IDF；中文按字符 2~3 元切分，无需分词库）
- 新增混合检索 `search_hybrid`：三种方法各自归一化后加权合成总分，权重可调；
  被多个方法命中时列出多条原因
- 语义检索新增 `min_score` 相似度下限，过滤不相关结果
- 新增课程归属（半自动）：`courses` 表 + `course.py` 的 `suggest_course`
  （从文件名「课程名_内容」抽课程名）；导入时自动写 `files.suggested_course_id`
- 界面新增「课程归属」区：逐条确认 / 修改最终课程，写入 `files.course_id`
- `files` 表新增 `suggested_course_id` / `course_id` 两列，保留系统建议与用户修正（D-012）
- 向量持久化：`files` 表新增 `embedding` / `embedding_model` 两列，向量算一次存库，
  语义检索与聚类直接读，不再每次现算
- 新增 `studyorganizer/index.py`：`ensure_embeddings()`（补算漏的 / 过期重算）与
  `import_and_index()`（导入 + 建索引）
- 向量过期的两种触发，判断统一成一条查询：正文变了（`save_file` 的 upsert 自动清空）、
  换模型了（`embedding_model` 与当前模型名对不上）
- 界面导入改用 `index.import_and_index`；启动时自动补一次索引，
  升级前导入的老库不用手动重导
- 新增 `tests/test_index.py`（6 个用例，覆盖上述四种过期情况 + 导入建索引）
- 段落级向量：新增 `studyorganizer/chunk.py`（`chunk_text()` 切段）与 `chunks` 表，
  由 `index.ensure_chunk_embeddings()` 负责切段 + 补向量
- `chunks` 表结构与 `files` 表对称（`embedding` + `embedding_model`），过期判断同一套；
  正文变了则把该文件的段落整批删掉，下次重新切、重新算
- 语义检索 `search_semantic` 改为**按段落**匹配：丢掉低于 `min_score` 的段落，
  同文件取最好的 3 段平均当文件分；原因里带上命中的段号与片段
- `practice/` 新增两个长样本：`算法_动态规划长讲义.txt`（4159 字 → 22 段）、
  `操作系统_进程调度长讲义.pdf`（5 页，每页一个「自然段」→ 二次切分）
- 新增 `tests/test_chunk.py`（10 个用例）；`test_index.py` 补 5 个段落后端用例；
  `test_search.py` 补 6 个「段落合成文件分」用例
- 新增 `tools/benchmark.py`：检索实测脚本（手动跑，不进 pytest）。走真正的生产路径
  建库（`index.import_and_index`）并调**真的** `search_semantic()`，报告「每条查询的
  标准答案排第几」、段落级间距、阈值扫描、编码耗时、模型体积；`--model` 可换模型对比。
  用临时数据库（把工作目录切到临时目录，`store._DB_PATH` 是相对路径），
  **绝不碰仓库里的 `studyorganizer.db`**，跑完还会核对它的指纹
- 内置 6 条带标准答案的测试查询，依据逐条写在注释里——**都是打开文件读过后标的**。
  其中「动态规划的状态应该怎么定义」就是 NOTES 第 8 条里我标错的那条，
  现在把 4 个正确答案都填上，变成一条正规用例
- 用它对三个模型做了完整对照（见 DESIGN.md）：旧模型 4/6、bge-small 6/6、bge-base 6/6

### Fixed
- **向量读取没有核对 `embedding_model`，会读出别的模型算的向量。**
  `list_file_vectors` / `list_chunk_vectors` 原先只查 `embedding IS NOT NULL`。
  正常路径上不会出事（`app.py` 启动时先跑完 `ensure_*` 才渲染搜索框），但换模型
  要把全库重算几十秒，用户等不及 Ctrl-C 中断后，库里会混着两种模型的向量
  （旧 768 维 / 新 512 维），`np.vstack` 直接崩
  `ValueError: Incompatible dimension for X and Y matrices`。
  现在两个读函数都带 `AND embedding_model IS ?`，只返回当前模型的向量，
  口径和 `list_*_needing_embedding` 完全一致（写和读用同一个判断）。
  `model_name` 是**必填参数**，从 `search` / `plan → cluster` 一路透传，
  `app.py` 传 `search.MODEL_NAME`——忘了传会当场报错，不会悄悄退化成不过滤。
  实测：中断状态下 `search_semantic` 不再崩，返回 0 条（暂时读不到），
  `cluster_files` 正常，补跑 `ensure_chunk_embeddings()` 后检索结果与之前完全一致。
  新增 `test_读向量时只认当前模型`（并用变异测试确认它不是空测试）。
- 语义分数是 numpy `float32`，直接 `round` 后打印成长小数
  （如 `0.5419999957084656`），显示前先转 `float`
- `save_file` 由 `INSERT OR REPLACE` 改为 `INSERT ... ON CONFLICT(path) DO UPDATE`：
  原先重复导入会把用户确认的 `course_id` 抹成 NULL
- `list_files_without_chunks` 原先用 SQL 的 `trim(text) != ''` 判断正文是否为空，
  但 **SQLite 的 `trim()` 只去空格、不去换行**，导致「正文只有几个换行」的文件
  每次都被当成没切过、反复重切（切又切不出段，永远轮不到它被标记成已处理）。
  判断挪到 Python 里用 `str.strip()`

### Changed
- 移出第一版范围：相似文件检测（含字节哈希 / SimHash / 语义相似三层去重）。
- 删除 README「第一版暂不做」小节。
- 界面结构命名统一：入口 `app.py` + 组件目录 `ui/`（原 `app/` 易混淆，见 D-013）。
- `init_db` 对已存在的老库自动 `ALTER TABLE` 补列（幂等，可反复调用）。
- 语义检索 `search_semantic` 与聚类 `cluster_files` 改为读库里的向量，不再现算；
  `cluster_files` 因此不再依赖向量模型。
- `search.py` 的 `_get_model` / `_MODEL_NAME` 改为公开的 `get_model` / `MODEL_NAME`，
  供 `index.py` 复用（私有名字跨模块用不合适）。
- `requirements.txt` 补上 `numpy`（`search.py` / `cluster.py` / `index.py` 直接用它）。
- `search_semantic` 的 `min_score` 默认值由 `0.3` 提到 `0.45`。这是**实测校准**的结果：
  在 `practice/` 语料上，`0.3` 会让 99% 的段落过关、等于没过滤；`0.45` 能砍掉明显
  跑题的尾部（详见 DESIGN.md「检索结果怎么从段落合成到文件」）。
- `app.py` 启动时同时补文档向量和段落向量，导入走 `index.import_and_index`（不变）。
- **语义向量模型换成 `BAAI/bge-small-zh-v1.5`**（原 `shibing624/text2vec-base-chinese`）。
  在 `practice/` 语料（22 文件 141 段）上实测：6 条带标准答案的查询里，旧模型只有
  4 条把答案排在第一（「过拟合怎么解决」那条正确答案掉到第 4），新模型 6 条全对；
  同样卡 0.45 的放行率从 49% 降到 27%。附带好处：体积 92 MB vs 390 MB、
  编码 141 段 1.2s vs 4.7s（都小/快了 4 倍）。评测过 `bge-base-zh-v1.5`
  （放行率能压到 14%，但**排序没比 bge-small 好**——一样 6/6，却要 8 倍体积、
  6 倍耗时）和 BGE 的查询前缀（实测只是把所有分数统一往下推，间距没变好，故未采用），
  详见 DESIGN.md。
  换模型**没有写任何迁移代码**——`embedding_model` 与当前模型名对不上，
  `ensure_*` 就把文档向量和段落向量全部重算（已实测验证）。
- 上面这些数字原先出自用完就删的一次性脚本，**谁也复现不了**；现在全部改由
  `tools/benchmark.py` 产出，并写明指标定义。原先的「74% / 31%」是拿 3 条查询按
  "每条平均"算的、定义没写下来，重跑对不上（旧模型实际是 49%），所以整表换口径，
  并补上更有说服力的「排第 1 的查询数」一列。DESIGN.md 的「间距」说法也跟着改了：
  原先写"合成到文件级会从 +0.11~+0.13 磨到 +0.05~+0.07"，实测其实**并不一致**——
  第 6 条 +0.243 → +0.110，第 1 条反而从 -0.016 升到 +0.040，改成如实描述，
  并点明这个余量不能当质量指标用
- README（中英）同步：模型对照、相对阈值的举例数字、「端到端测试」那条都换成
  可复现的说法，项目结构树补上 `tools/`
