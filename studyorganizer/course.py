"""course 模块：猜课程归属（半自动，规则打底）。

给一个文件名，猜它属于哪门课。例：算法_图论最短路径.txt → 算法
猜不出来就返回 None（比如「笔记1.txt」这种没线索的名字）。

以后会加统一接口，接入更聪明的建议方式（如语义/聚类），见 DECISIONS D-007。
"""

import os


def suggest_course(filename):
    """
    根据文件名猜课程名。
    规则：文件名形如「课程名_内容」，取第一个分隔符前的那段当课程名。
    返回课程名字符串；猜不出返回 None。
    """
    name = os.path.basename(filename)     # 去掉目录，只要文件名
    name = os.path.splitext(name)[0]      # 去掉扩展名

    for sep in ("_", "-"):                # 常见的两种分隔符
        if sep in name:
            head = name.split(sep)[0].strip()   # 第一段
            if _looks_like_course(head):
                return head
    return None


def _looks_like_course(head):
    """
    简单护栏：过滤掉明显不像课程名的第一段。
    例：2023-期末试卷.txt → 第一段是「2023」，那是年份不是课程。
    """
    if not head:
        return False
    if head.isdigit():                    # 纯数字（年份 / 编号）
        return False
    if len(head) > 12:                    # 课程名一般不长，太长多半是整句话
        return False
    return True
