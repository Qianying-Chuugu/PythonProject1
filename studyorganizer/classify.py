"""classify 模块：判断资料类型。

这是 StudyOrganizer 的第二个模块，负责"分类"。
目前用关键词规则判断类型（讲义/作业/试卷/笔记/实验报告），
以后会加统一接口，接入 ML 分类器。
"""

# 每种类型的"关键词"：命中哪个词，就计一票
_RULES = {
    "讲义": ["讲义", "课件", "章节"],
    "作业": ["作业", "习题", "解答"],
    "试卷": ["试卷", "期末", "期中", "考试", "得分", "学号"],
    "笔记": ["笔记", "总结", "复习", "重点"],
    "实验报告": ["实验", "报告", "目的", "原理", "步骤", "结论"],
}


def classify_type(title, text):
    """判断资料类型，返回：讲义/作业/试卷/笔记/实验报告/未知。"""
    content = title + " " + text              # 标题+正文拼一起

    scores = {}
    for doc_type, keywords in _RULES.items():
        score = 0
        for kw in keywords:
            if kw in content:
                score += 1
        scores[doc_type] = score

    best_type = "未知"                        # 找最高分
    best_score = 0
    for doc_type, score in scores.items():
        if score > best_score:
            best_score = score
            best_type = doc_type

    return best_type
