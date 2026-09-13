"""测 plan 模块：生成整理方案、导出报告。

这里把聚类和数据库都换成假的，测的是 plan 自己的逻辑：
哪几组该生成建议、标题怎么拼、导出时挑哪些条目。
"""

from studyorganizer import plan, store


def test_生成方案_只有一个文件的组被跳过(monkeypatch):
    added = []

    def fake_cluster_files(threshold=0.3):
        return {0: ["讲义A", "讲义B"], 1: ["孤零零的笔记"]}

    def fake_add_plan_item(action, files, reason, db_path=store._DB_PATH):
        added.append((action, files, reason))

    monkeypatch.setattr(plan, "cluster_files", fake_cluster_files)
    monkeypatch.setattr(store, "clear_plan_items", lambda db_path=store._DB_PATH: None)
    monkeypatch.setattr(store, "add_plan_item", fake_add_plan_item)
    monkeypatch.setattr(store, "list_plan_items", lambda db_path=store._DB_PATH: [])

    plan.generate_plan()

    # 只有 2 个文件的那组才值得「归并」；单个文件没得归并
    assert len(added) == 1
    assert added[0] == ("归并", "讲义A、讲义B", "内容语义相近")


def test_生成方案_先清空旧建议再生成新的(monkeypatch):
    order = []

    def fake_clear_plan_items(db_path=store._DB_PATH):
        order.append("清空")

    def fake_add_plan_item(action, files, reason, db_path=store._DB_PATH):
        order.append("新增")

    monkeypatch.setattr(plan, "cluster_files", lambda threshold=0.3: {0: ["A", "B"]})
    monkeypatch.setattr(store, "clear_plan_items", fake_clear_plan_items)
    monkeypatch.setattr(store, "add_plan_item", fake_add_plan_item)
    monkeypatch.setattr(store, "list_plan_items", lambda db_path=store._DB_PATH: [])

    plan.generate_plan()

    # 顺序很重要：不清掉旧的，重新生成就会出现重复建议
    assert order == ["清空", "新增"]


def test_导出报告_只导出已确认的(monkeypatch, tmp_path):
    items = [
        (1, "归并", "讲义A、讲义B", "内容语义相近", "confirmed"),
        (2, "归并", "笔记C、笔记D", "内容语义相近", "pending"),
        (3, "归并", "试卷E、试卷F", "内容语义相近", "rejected"),
    ]

    monkeypatch.setattr(store, "list_plan_items", lambda db_path=store._DB_PATH: items)

    out = tmp_path / "整理方案.md"
    n = plan.export_report(str(out))

    assert n == 1                                  # 3 条里只有 1 条已确认

    content = out.read_text(encoding="utf-8")
    assert "讲义A" in content
    assert "笔记C" not in content                   # pending 的不导出
    assert "试卷E" not in content                   # rejected 的也不导出


def test_导出报告_没有已确认的就返回0且不建文件(monkeypatch, tmp_path):
    items = [(1, "归并", "讲义A、讲义B", "内容语义相近", "pending")]
    monkeypatch.setattr(store, "list_plan_items", lambda db_path=store._DB_PATH: items)

    out = tmp_path / "不该被创建.md"

    assert plan.export_report(str(out)) == 0
    assert not out.exists()                        # 一条都没确认，就不该产出文件
