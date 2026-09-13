"""测标签：自动标签、用户改标签、以及「去掉」这件事到底留下了什么。

这里用真的 SQLite 库（tmp_path 里的临时文件），因为要测的正是
「写进去的和读出来的是不是一回事」——把 store 换成假的就测不出来了。
（test_store.py 那个写死文件名、不清理的老写法不要跟，见 test_index.py 的做法。）

最该盯住的一条：**自动标签绝不能被重新导入激活**（见 test_重新导入...）。
"""

from studyorganizer import store


def _建库(tmp_path):
    """在临时目录建一个空库，返回它的路径。"""
    db = str(tmp_path / "test.db")
    store.init_db(db)
    return db


def _存文件(db, path="a.txt", title="讲义A"):
    """存一个文件进库，返回它的 id（自动标签要挂在 id 上）。"""
    return store.save_file({"path": path, "title": title, "text": "正文"}, db)


def _标签(db, file_id):
    """这个小文件身上的标签，写成 {标签名: (来源, 状态)} 方便比对。

    用元组比字符串好：来源和状态得分开断言，不然 "auto" 和 "active" 会看混。
    """
    return {name: (source, status)
            for fid, name, source, status in store.list_file_tags(db)
            if fid == file_id}


# ---------- 用户手输标签 ----------

def test_用户加的标签记成user(tmp_path):
    db = _建库(tmp_path)
    fid = _存文件(db)

    store.set_file_tags(fid, ["算法", "重点"], db)

    assert _标签(db, fid) == {"算法": ("user", "active"), "重点": ("user", "active")}


def test_标签名会洗干净_去空格去重去空串(tmp_path):
    db = _建库(tmp_path)
    fid = _存文件(db)

    # 用户在输入框里手打的，前后带空格、重复、还留了个空的，都算正常输入
    store.set_file_tags(fid, [" 算法 ", "算法", "", "  "], db)

    assert _标签(db, fid) == {"算法": ("user", "active")}


def test_同名标签不会重复建(tmp_path):
    db = _建库(tmp_path)
    a = _存文件(db, "a.txt")
    b = _存文件(db, "b.txt")

    store.set_file_tags(a, ["重点"], db)
    store.set_file_tags(b, ["重点"], db)

    assert len(store.list_tags(db)) == 1               # 两个文件共用一个标签行
    assert store.get_or_create_tag("重点", db) == store.list_tags(db)[0][0]


# ---------- 去掉标签：两种来源，两种待遇 ----------

def test_去掉自动标签是翻状态不是删行(tmp_path):
    """D-012 的核心：用户拒绝要留痕，所以行必须还在（只是 status 变了）。"""
    db = _建库(tmp_path)
    fid = _存文件(db)
    store.add_auto_tag(fid, "讲义", db)

    store.set_file_tags(fid, [], db)                   # 用户一个标签都不选 = 全去掉

    assert _标签(db, fid) == {"讲义": ("auto", "rejected")}
    # 说明一下为什么不是 {}：行删了的话，「用户拒过什么」这条信息就永久没了，
    # 将来拿它训练分类器（D-006）也就无从谈起。


def test_去掉自己的标签就整行删掉(tmp_path):
    """用户自己加的东西，自己撤了，没有留痕价值。"""
    db = _建库(tmp_path)
    fid = _存文件(db)
    store.set_file_tags(fid, ["重点"], db)

    store.set_file_tags(fid, [], db)

    assert _标签(db, fid) == {}
    # 但标签本身留着：别的文件可能还在用同一个名字，删了会连带把别人的标签也弄丢
    assert [name for _id, name in store.list_tags(db)] == ["重点"]


def test_重新选上被拒的自动标签_来源不变(tmp_path):
    db = _建库(tmp_path)
    fid = _存文件(db)
    store.add_auto_tag(fid, "讲义", db)
    store.set_file_tags(fid, [], db)                   # 拒了

    store.set_file_tags(fid, ["讲义"], db)             # 又改主意了

    # 状态回到 active，但 source 仍是 auto——它本来就是系统判的，
    # 用户只是"又要了"，不等于"这是我手输的"（D-012：两者的区别要保住）
    assert _标签(db, fid) == {"讲义": ("auto", "active")}


# ---------- 自动标签：重新导入不能改变已有记录 ----------

def test_重新导入不会让被拒的自动标签复活(tmp_path):
    """本轮风险最高的一条。

    doc_type 每次导入都会重算，所以 add_auto_tag 会被反复叫到同一个文件上。
    如果它写成「重新对齐」（先删后插 / INSERT OR REPLACE），用户上次特意去掉的
    标签就会被下一次导入**悄无声息**地装回去——没有提示、没有痕迹。
    """
    db = _建库(tmp_path)
    fid = _存文件(db)
    store.add_auto_tag(fid, "讲义", db)
    store.set_file_tags(fid, [], db)                   # 用户拒掉它

    store.add_auto_tag(fid, "讲义", db)                # 过几天重新导入一遍，又判成「讲义」

    assert _标签(db, fid) == {"讲义": ("auto", "rejected")}    # 还是拒着的


def test_自动标签不会覆盖同名的手动标签(tmp_path):
    db = _建库(tmp_path)
    fid = _存文件(db)
    store.set_file_tags(fid, ["重点"], db)             # 用户先手输了一个「重点」

    store.add_auto_tag(fid, "重点", db)                # 分类器后来也判出「重点」

    assert _标签(db, fid) == {"重点": ("user", "active")}      # 来源还是 user


# ---------- 导入时会自动挂上类型标签 ----------

def test_导入文件夹会自动打上类型标签(tmp_path):
    db = _建库(tmp_path)
    folder = tmp_path / "practice"
    folder.mkdir()
    (folder / "算法_讲义.txt").write_text("这是讲义的正文", encoding="utf-8")

    store.import_folder(str(folder), db)

    fid, _path, _title, doc_type = store.list_files(db)[0]
    assert doc_type == "讲义"                            # 分类器的判断
    assert _标签(db, fid) == {"讲义": ("auto", "active")}       # 同一个词挂成了自动标签
