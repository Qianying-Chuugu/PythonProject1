"""plan 模块：生成整理方案。

把聚类结果翻译成"给用户的建议清单"。
"""

from studyorganizer import store
from studyorganizer.cluster import cluster_files


def generate_plan():
    """生成整理方案：把聚类出来的每一堆，翻译成一条"归并建议"。

    返回 [(id, action, files, reason, status), ...]
    """
    groups = cluster_files()          # {堆号: [标题列表]}
    store.clear_plan_items()          # 先清掉旧的，避免重复

    for titles in groups.values():
        if len(titles) > 1:           # 单个文件没得归并，跳过
            store.add_plan_item(
                action="归并",
                files="、".join(titles),
                reason="内容语义相近",
            )

    return store.list_plan_items()


def confirm_plan():
    """命令行交互：逐条确认或拒绝整理建议。"""
    items = store.list_plan_items()
    for item_id, action, files, reason, status in items:
        if status != "pending":
            continue                    # 已经处理过的跳过
        print(f"\n{action}：{files}")
        answer = input("确认(y) / 拒绝(n) / 跳过(回车)？ ")
        if answer == "y":
            store.set_plan_status(item_id, "confirmed")
            print("  已确认 ✓")
        elif answer == "n":
            store.set_plan_status(item_id, "rejected")
            print("  已拒绝 ✗")
        else:
            print("  跳过（保持 pending）")
