"""测 plan 模块：生成整理方案、导出报告。

这里把聚类和数据库都换成假的，测的是 plan 自己的逻辑：
哪几组该生成建议、标题怎么拼、导出时挑哪些条目。
"""

from studyorganizer import plan, store

_假模型 = "假模型"   # generate_plan 要把它透传给 cluster_files


def test_生成方案_只有一个文件的组被跳过(monkeypatch):
    added = []

    def fake_cluster_files(model_name, threshold=0.3):
        assert model_name == _假模型      # 确认名字一路传到了聚类那儿
        return {0: ["讲义A", "讲义B"], 1: ["孤零零的笔记"]}

    def fake_add_plan_item(action, files, reason, db_path=store._DB_PATH):
        added.append((action, files, reason))

    monkeypatch.setattr(plan, "cluster_files", fake_cluster_files)
    monkeypatch.setattr(store, "clear_plan_items", lambda db_path=store._DB_PATH: None)
    monkeypatch.setattr(store, "add_plan_item", fake_add_plan_item)
    monkeypatch.setattr(store, "list_plan_items", lambda db_path=store._DB_PATH: [])

    plan.generate_plan(_假模型)

    # 只有 2 个文件的那组才值得「归并」；单个文件没得归并
    assert len(added) == 1
    assert added[0] == ("归并", "讲义A、讲义B", "内容语义相近")


def test_生成方案_先清空旧建议再生成新的(monkeypatch):
    order = []

    def fake_clear_plan_items(db_path=store._DB_PATH):
        order.append("清空")

    def fake_add_plan_item(action, files, reason, db_path=store._DB_PATH):
        order.append("新增")

    monkeypatch.setattr(plan, "cluster_files", lambda model_name, threshold=0.3: {0: ["A", "B"]})
    monkeypatch.setattr(store, "clear_plan_items", fake_clear_plan_items)
    monkeypatch.setattr(store, "add_plan_item", fake_add_plan_item)
    monkeypatch.setattr(store, "list_plan_items", lambda db_path=store._DB_PATH: [])

    plan.generate_plan(_假模型)

    # 顺序很重要：不清掉旧的，重新生成就会出现重复建议
    assert order == ["清空", "新增"]


def test_生成方案_不会去查文件表(monkeypatch):
    """回归：generate_plan 只该依赖聚类结果，不该顺手去扫 files 表。

    曾经有过一版「打标签」建议，会调 store.list_files / list_files_with_course。
    那个写法有个隐患——上面几条测试把这些函数桩掉了，可真跑起来它们读的是
    **真正的 studyorganizer.db**，测试结果就跟着用户的实际数据变了。
    这版删掉了那遍分组，这里用"把这两个函数换成会爆炸的桩"来钉住它不会被加回来。
    """
    def 不该被调用(*args, **kwargs):
        raise AssertionError("generate_plan 不该去读 files 表")

    monkeypatch.setattr(plan, "cluster_files", lambda model_name, threshold=0.3: {0: ["A", "B"]})
    monkeypatch.setattr(store, "clear_plan_items", lambda db_path=store._DB_PATH: None)
    monkeypatch.setattr(store, "add_plan_item", lambda *a, **k: None)
    monkeypatch.setattr(store, "list_plan_items", lambda db_path=store._DB_PATH: [])
    monkeypatch.setattr(store, "list_files", 不该被调用)
    monkeypatch.setattr(store, "list_files_with_course", 不该被调用)

    plan.generate_plan(_假模型)      # 不炸就算过


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


def test_导出报告_带上动作和原因(monkeypatch, tmp_path):
    """报告的小标题用条目自己的 action，不能再硬写「## 组N」。

    「组」只说"这是第几堆"，action 说的才是"建议你干嘛"。reason 以前也被整个
    丢掉了——用户在报告里只看得到一串文件名，看不到为什么建议这么干。
    """
    items = [
        (1, "归并", "讲义A、讲义B", "内容语义相近", "confirmed"),
        (2, "归并", "笔记C、笔记D", "内容语义相近", "confirmed"),
    ]
    monkeypatch.setattr(store, "list_plan_items", lambda db_path=store._DB_PATH: items)

    out = tmp_path / "整理方案.md"
    plan.export_report(str(out))
    content = out.read_text(encoding="utf-8")

    assert "## 1. 归并" in content
    assert "## 2. 归并" in content
    assert "## 组1" not in content                  # 旧格式不许回来
    assert "（内容语义相近）" in content


def test_导出报告_没有已确认的就返回0且不建文件(monkeypatch, tmp_path):
    items = [(1, "归并", "讲义A、讲义B", "内容语义相近", "pending")]
    monkeypatch.setattr(store, "list_plan_items", lambda db_path=store._DB_PATH: items)

    out = tmp_path / "不该被创建.md"

    assert plan.export_report(str(out)) == 0
    assert not out.exists()                        # 一条都没确认，就不该产出文件
