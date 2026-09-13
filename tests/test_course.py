"""测 course 模块的 suggest_course：从文件名猜课程名。

猜的规则是「课程名_内容」，取第一个分隔符前的那段。
猜不出就返回 None（宁可不猜，也不要猜错）。
"""

from studyorganizer.course import suggest_course


def test_从文件名猜出课程():
    # 文件名格式「课程名_内容」，取第一段当课程名
    assert suggest_course("算法_图论最短路径.txt") == "算法"
    assert suggest_course("软件工程_需求分析讲义.txt") == "软件工程"


def test_短横线也能当分隔符():
    assert suggest_course("高等数学-微积分作业.txt") == "高等数学"


def test_只看文件名不看目录():
    # 前面有目录时，应该只看文件名那一段
    assert suggest_course("practice/算法_图论最短路径.txt") == "算法"


def test_没有分隔符就猜不出():
    assert suggest_course("笔记1.txt") is None


def test_纯数字的第一段不算课程名():
    # 「2023-期末试卷」的第一段是年份，不是课程
    assert suggest_course("2023-期末试卷.txt") is None


def test_第一段太长就不算课程名():
    # 课程名一般很短，超过 12 个字的多半是整句话，别乱猜
    assert suggest_course("这是一句特别特别特别长的话_内容.txt") is None


def test_分隔符前面是空的也猜不出():
    assert suggest_course("_内容.txt") is None
