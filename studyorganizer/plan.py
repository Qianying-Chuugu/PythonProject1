"""plan 模块：生成整理方案。

把聚类结果翻译成"给用户的建议清单"。
"""

from studyorganizer import store
from studyorganizer.cluster import cluster_files


def generate_plan(model_name):
    """生成整理方案：把聚类出来的每一堆，翻译成一条"归并建议"。

    参数 model_name：当前向量模型名，传给聚类用（见 cluster 模块说明）。
    返回 [(id, action, files, reason, status), ...]

    **不生成「打标签」类的建议。** 曾经做过一版：按「课程 + 类型」分组，提醒用户
    给这几份文件打标签。删掉的原因是它要么重复、要么越界——
      · 把课程名也当标签，等于让用户把课程归属记两遍（课程已经有自己的表和确认
        流程，见 D-014）；
      · 去掉课程、只按类型分组，那又跟导入时自动打的类型标签重复（`import_folder`
        已经给每份文件记了 `source='auto'` 的类型标签）。
    标签这条路就两条：**导入时自动检测 + 用户在界面「标签」区手动改**，到此为止。
    """
    groups = cluster_files(model_name)   # {堆号: [标题列表]}
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


def export_report(path="整理方案.md"):
    """把已确认的整理建议导出成 markdown 报告，返回导出的条数。"""
    items = store.list_plan_items()

    # 只挑出已确认的
    confirmed = []
    for item in items:
        if item[4] == "confirmed":
            confirmed.append(item)

    if not confirmed:
        return 0

    # 拼出报告内容
    # 小标题用**条目自己的 action**（「## 1. 归并」），不再硬写「## 组N」——
    # 「组」没说这条建议要干嘛，而 action 本来就是"要干嘛"。现在就一种 action，
    # 但以后再加（重命名等）报告不用跟着改格式。
    # reason 也一并带上：它就是给用户看的那句"为什么建议这么干"，
    # 以前导出时被丢掉了，报告里只剩一串文件名和序号，等于让人猜。
    lines = [f"# 整理方案（已确认 {len(confirmed)} 条）", ""]
    n = 0
    for item in confirmed:
        n += 1
        _id, action, files, reason, status = item
        lines.append(f"## {n}. {action}")
        if reason:
            lines.append(f"（{reason}）")
        for f in files.split("、"):        # 每个文件一行
            lines.append(f"- {f}")
        lines.append("")

    # 写进文件
    report = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)

    return len(confirmed)
