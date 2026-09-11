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

### Changed
- 移出第一版范围：相似文件检测（含字节哈希 / SimHash / 语义相似三层去重）。
- 删除 README「第一版暂不做」小节。
- 界面结构命名统一：入口 `app.py` + 组件目录 `ui/`（原 `app/` 易混淆，见 D-013）。
