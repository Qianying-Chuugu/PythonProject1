# ROADMAP

## 版本规划

- **v0.1（当前阶段）**：本地单机版，核心链路跑通，全部离线，不移动原文件。
- **v0.2**：把核心能力封装为 FastAPI 接口。
- **v0.3+**：接入大模型（如把检索/分类证据交给 LLM 生成说明）、OCR、更多格式等。

## v0.1 目标

实现「导入 → 提取 → 分类打标签 → 建索引 → 检索 → 整理方案」的完整闭环。

## 任务清单

> 勾选标记：[x] 已完成；[~] 部分完成（括号说明已做/未做）；[ ] 未开始。
> 本清单已于 2026-09-13 对照代码对齐，之前部分标记滞后于实际实现。

### 基础设施
- [x] 项目骨架与模块划分（核心包 + Streamlit 壳分离）
- [~] SQLite 表结构（已做 files / plan_items / courses / chunks；tags / file_tags 未做）
- [ ] 日志与可复现性（固定随机种子）

### 文本提取
- [x] TXT / Markdown 提取（含编码探测 charset-normalizer）
- [x] PDF 提取（PyMuPDF）
- [x] 标题提取与文件名清洗
- [x] 扫描件（无文本层 PDF）识别与提示

### 分类
- [ ] 统一分类接口抽象（TypeClassifier）
- [x] 规则分类器（讲义 / 作业 / 试卷 / 笔记 / 实验报告）
- [x] 课程候选建议（CourseSuggester，半自动；规则打底：从文件名抽课程名）
- [~] 用户修改 → 回写数据库（课程已做；标签未做）
- [~] 建议值与用户修正分开落库（课程已做 suggested_course_id / course_id；标签未做）

### 向量与索引
- [x] 文档级向量（用于聚类；已持久化到 `files.embedding`）
- [x] 段落级向量（用于语义检索；`chunk.py` 切段 + 持久化到 `chunks.embedding`）
- [x] 向量持久化与「过期重算」判断（正文变了 / 换模型 → 自动重算，见 DESIGN.md）
- [ ] 固定模型缓存路径（模型已由 sentence-transformers 默认缓存，离线可用；未显式固定路径）
- [x] **换区分度更强的中文模型**。已换成 `BAAI/bge-small-zh-v1.5`（实测见 DESIGN.md）：
      同样卡 0.45，放行率从 74% 降到 31%、间距翻倍到三倍，而且体积小 4 倍、编码快 4 倍。
      换模型没写任何迁移代码——`embedding_model` 对不上就自动全部重算，上一阶段铺的路用上了
- [x] 向量读函数也核对 `embedding_model`：`list_file_vectors(model_name)` /
      `list_chunk_vectors(model_name)` 只返回当前模型算的向量，名字从
      `search` / `plan → cluster` 一路透传。换模型重算到一半被打断时，
      原先会崩 `ValueError: Incompatible dimension`（768 混 512），
      现在只是暂时读不到，补跑一次 `ensure_*` 就恢复（实测验证过）。见 DESIGN.md
- [ ] **改成相对阈值**：`min_score` 是绝对分数线，实测分不干净——「0-1 背包的状态
      转移方程」这条，不相关段落里最高的（0.766）比答案里最高的（0.750）还高。
      可改成「只留明显高于全库平均的那些段」。
      动它之前先用 `tools/benchmark.py` 跑一组基线并记下来，不然改完没法知道变好没有
- [ ] 段落向量的向量索引（现在每次检索都把全库段落读进内存算余弦；几百~几千段够用，
      上万段就该换 FAISS 之类）

### 检索
- [ ] 统一检索接口抽象（Retriever）
- [x] 文件名关键词检索
- [x] 正文关键词检索（TF-IDF；BM25 未做）
- [x] 语义检索（按段落匹配；同一文件取最好的 3 段平均当文件分，见 DESIGN.md）
- [x] 混合检索与「匹配原因」输出

### 聚类
- [x] 聚类 → 整理方案依据（现为全局聚类，尚无「课程内」概念）

### 整理方案
- [~] 建议方案生成（已做归并；重命名 / 打标签未做）
- [x] 用户确认 / 拒绝
- [x] 确认后执行（v1 仅做安全操作：导出整理报告）

### 界面
- [~] app.py 入口 + ui/ 组件（入口已做；ui/ 组件目录未建，界面暂写在 app.py 里）

### 文档
- [x] README「运行方式」
- [x] 项目文档体系（README / DESIGN / DECISIONS / ROADMAP / CHANGELOG / NOTES）
- [x] 新手教程 `tutorial.md`（Python 语法，已到第九课 + 综合练习）

### 测试
- [x] pytest 覆盖核心模块（extract / chunk / classify / course / store / search / cluster / plan / index
      共 9 个；涉及向量模型的路径用假模型 / 假函数替掉，测试不联网、不下载模型）
- [x] 真实模型的端到端检索测试：做成手动脚本 `tools/benchmark.py`
      （要加载模型，不适合放进默认测试集，pytest 里仍旧用假模型替身；
      见 DESIGN.md「可复现性」）
- [~] 检索质量的回归断言：`tools/benchmark.py` 现在只打印报告、不断言
      （「标准答案必须排第 1」这类断言还没加，加了才能挡住"改检索改坏了"）
