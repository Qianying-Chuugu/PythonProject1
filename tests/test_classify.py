from studyorganizer.classify import classify_type


def test_讲义():
    assert classify_type("第3讲", "这是课件内容") == "讲义"


def test_作业():
    assert classify_type("作业1", "请解答") == "作业"


def test_试卷():
    assert classify_type("期末试卷", "姓名 学号 得分") == "试卷"


def test_笔记():
    assert classify_type("课堂笔记", "今天讲了") == "笔记"


def test_实验报告():
    assert classify_type("实验报告3", "实验目的 原理 步骤 结论") == "实验报告"


def test_未知():
    assert classify_type("随便一个", "完全没关键词") == "未知"
