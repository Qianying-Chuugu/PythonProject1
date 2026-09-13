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

### Fixed
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
  在 `practice/` 语料（22 文件 141 段）上实测：同样卡 0.45，旧模型放行 74% 的段落
  （阈值形同虚设），新模型只放行 31%；正确答案与不相关段落的间距从
  +0.085/+0.028/+0.060 提到 +0.133/+0.096/+0.110。附带好处：体积 92M vs 391M、
  编码 141 段 1.1s vs 4.5s（都小/快了 4 倍）。评测过 `bge-base-zh-v1.5`（间距只略好，
  但要 8 倍体积、6 倍耗时）和 BGE 的查询前缀（实测只是把所有分数统一往下推，
  间距没变好，故未采用），详见 DESIGN.md。
  换模型**没有写任何迁移代码**——`embedding_model` 与当前模型名对不上，
  `ensure_*` 就把文档向量和段落向量全部重算（已实测验证）。
