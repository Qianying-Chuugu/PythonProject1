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

### Fixed
- 语义分数是 numpy `float32`，直接 `round` 后打印成长小数
  （如 `0.5419999957084656`），显示前先转 `float`
- `save_file` 由 `INSERT OR REPLACE` 改为 `INSERT ... ON CONFLICT(path) DO UPDATE`：
  原先重复导入会把用户确认的 `course_id` 抹成 NULL

### Changed
- 移出第一版范围：相似文件检测（含字节哈希 / SimHash / 语义相似三层去重）。
- 删除 README「第一版暂不做」小节。
- 界面结构命名统一：入口 `app.py` + 组件目录 `ui/`（原 `app/` 易混淆，见 D-013）。
- `init_db` 对已存在的老库自动 `ALTER TABLE` 补列（幂等，可反复调用）。
