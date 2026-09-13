"""store 模块：用 SQLite 把文件信息存起来。

SQLite 是"存在一个文件里的数据库"，Python 自带 sqlite3，不用额外安装。
数据存进 .db 文件后，程序关了也还在，还能用 SQL 查询。
"""

import os
import sqlite3
from studyorganizer.extract import extract_file
from studyorganizer.classify import classify_type
from studyorganizer.course import suggest_course

_DB_PATH = "studyorganizer.db"

def init_db(db_path=_DB_PATH):  #建表SQL
    conn = sqlite3.connect(db_path) #链接
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (  
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            path TEXT NOT NULL UNIQUE,
            title TEXT,
            doc_type TEXT,
            text TEXT,
            is_scanned INTEGER DEFAULT 0,
            embedding BLOB,
            embedding_model TEXT
        )
    """)  #每行唯一一个编号,路径唯一,标题,正文,是否扫描件(默认0),向量,向量用的模型
    conn.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)  #课程表：一门课一行，name 唯一（不能重复建同一门课）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plan_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            files TEXT NOT NULL,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
        )
    """)  #整理方案：一行一条建议，files 存建议归并的文件标题
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            seq INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding BLOB,
            embedding_model TEXT,
            UNIQUE (file_id, seq)
        )
    """)  #段落表：一篇文章切成的若干段，每段一行
    #      file_id 指向 files.id（和 files.course_id 一样，只记关系不建外键约束）；
    #      seq 是段落在原文里的顺序，从 1 开始（这个号是给人看的「第几段」）；
    #      UNIQUE(file_id, seq) 保证同一文件里不会有重复段号。
    #      后两列和 files 表完全对称，过期判断用的是同一套办法（见 index.py）。
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)  #标签表：一个标签名一行，name 唯一（同一个标签名只存一条）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_tags (
            file_id INTEGER NOT NULL,
            tag_id  INTEGER NOT NULL,
            source TEXT NOT NULL,
            confidence REAL,
            status TEXT NOT NULL DEFAULT 'active',
            PRIMARY KEY (file_id, tag_id)
        )
    """)  #文件↔标签：多对多，所以单独一张表（一个文件多个标签、一个标签多个文件）
    #      file_id / tag_id 指向 files.id / tags.id，和 files.course_id 一样只记关系、
    #      不写 REFERENCES 约束（SQLite 外键默认不生效，写了也只是个注释，见 DESIGN.md）；
    #      PRIMARY KEY (file_id, tag_id) 保证同一对「文件+标签」只会有一行——
    #      自动标签能不能被重新导入激活，靠的就是这个主键 + INSERT OR IGNORE（见 add_auto_tag）；
    #      source 记这条是谁加的：'auto'（分类器判的）| 'user'（用户手输的）；
    #      confidence 是自动标签的置信度，**本轮恒为 NULL**——classify.py 的
    #      classify_type 只给一个类型名、不给分数，这里不假装算过。
    #      列先留着（D-012 和 DESIGN 草案都点名了它），等分类器真出分数了再填；
    #      status 记这条还有没有效：'active' | 'rejected'（用户去掉的自动标签把这行
    #      留着、只翻成 rejected，不删——D-012 要求拒绝留痕，D-006 要靠它沉淀训练数据）。
    # 这两张表**不需要像 files 那样 ALTER 补列**：上面就是 CREATE TABLE IF NOT EXISTS，
    # 本身就是幂等的，老库下次 init_db() 自动建上（跟当初加 chunks 走的是同一条路）。
    # files 当初要用 ALTER，是因为它加的是**列**——表已经存在时 CREATE 不会加列。
    # 给老库补上后加的列。注意：表已经存在时，CREATE TABLE IF NOT EXISTS 不会加列，
    # 所以老数据库（studyorganizer.db）得用 ALTER TABLE 补，否则会报"no such column"。
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(files)")}  # 现在有哪些列
    for col, col_type in (
        ("suggested_course_id", "INTEGER"),
        ("course_id", "INTEGER"),
        ("embedding", "BLOB"),          # 文档级向量（存成字节），聚类和语义检索用
        ("embedding_model", "TEXT"),    # 这行的向量是哪个模型算的，用来判断要不要重算
    ):
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE files ADD COLUMN {col} {col_type}")
    conn.commit()  #保存
    conn.close()  #关闭


def save_file(info, db_path=_DB_PATH):
    """
    把 extract_file 返回的字典存进数据库。
    info 里要有：path、title、text
    （doc_type、is_scanned、suggested_course_id 可选，没有就存 NULL）
    返回这个文件在库里的 id（新建的是新 id，已存在的还是原来那个 id）——
    导入时要拿它去挂自动标签，所以必须有。
    """
    conn = sqlite3.connect(db_path)

    # 先看一眼这个路径存过没有、正文跟之前一不一样——用来判断段落要不要作废。
    row = conn.execute("SELECT id, text FROM files WHERE path = ?", (info["path"],)).fetchone()
    old_id = row[0] if row else None
    text_changed = row is not None and row[1] != info["text"]

    # 用 ON CONFLICT DO UPDATE（不是 INSERT OR REPLACE）。
    # REPLACE 是先删旧行再插新行，没列出的 course_id（用户确认值）会被抹成 NULL；
    # DO UPDATE 只改下面列出的这几列，course_id 原样保留，符合 D-012。
    conn.execute(
        "INSERT INTO files"
        " (path, title, doc_type, text, is_scanned, suggested_course_id)"
        " VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(path) DO UPDATE SET"
        "   title = excluded.title,"
        "   doc_type = excluded.doc_type,"
        "   text = excluded.text,"
        "   is_scanned = excluded.is_scanned,"
        "   suggested_course_id = excluded.suggested_course_id,"
        # 正文没变 → 向量照旧留着（重复导入不会白白重算）；
        # 正文变了 → 把向量和模型名一起清空，等于插一面「这行过期了」的旗子，
        #            index.ensure_embeddings() 看到 NULL 就会重算它。
        "   embedding = CASE WHEN files.text IS excluded.text"
        "                    THEN files.embedding ELSE NULL END,"
        "   embedding_model = CASE WHEN files.text IS excluded.text"
        "                        THEN files.embedding_model ELSE NULL END",
        (info["path"], info["title"], info.get("doc_type"), info["text"],
         1 if info.get("is_scanned") else 0, info.get("suggested_course_id")),
    )

    if text_changed:
        # 正文变了，按旧正文切出来的段就全不作数了——整批删掉，
        # 等 index.ensure_chunk_embeddings() 拿新正文重新切、重新算。
        # 这样「换个切法重来」也不需要写迁移代码，删掉重导即可。
        conn.execute("DELETE FROM chunks WHERE file_id = ?", (old_id,))

    # 再按 path 查一次拿 id。不图省事用 cur.lastrowid：走 DO UPDATE 分支时
    # lastrowid 是"更新那一行"的 rowid，虽然碰巧也对，但查一次是明确的、不受
    # 插入/更新分支影响，读代码的人不用去想 SQLite 这种情况下 lastrowid 到底是啥。
    file_id = conn.execute("SELECT id FROM files WHERE path = ?", (info["path"],)).fetchone()[0]
    conn.commit()
    conn.close()
    return file_id


def get_or_create_course(name, db_path=_DB_PATH):
    """按课程名查课程 id；没有就新建一条。返回 course id。"""
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT id FROM courses WHERE name = ?", (name,)).fetchone()
    if row:
        course_id = row[0]
    else:
        cur = conn.execute("INSERT INTO courses (name) VALUES (?)", (name,))
        course_id = cur.lastrowid       # 刚插入那行的 id
    conn.commit()
    conn.close()
    return course_id


def list_courses(db_path=_DB_PATH):
    """返回所有课程 (id, name)，按名字排序。"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, name FROM courses ORDER BY name").fetchall()
    conn.close()
    return rows


def set_file_course(file_id, course_id, db_path=_DB_PATH):
    """把用户最终确认的课程写进 files.course_id（确认或修改时调用）。"""
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE files SET course_id = ? WHERE id = ?", (course_id, file_id))
    conn.commit()
    conn.close()


def list_files(db_path=_DB_PATH):
    """返回数据库里所有文件的 (id, path, title, doc_type)。"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, path, title, doc_type FROM files").fetchall()
    conn.close()
    return rows


def list_files_with_course(db_path=_DB_PATH):
    """
    返回所有文件 + 课程信息，供界面显示。
    每行：(文件id, 标题, 建议课程名, 已确认课程名)
    用 LEFT JOIN：没建议、没确认的字段就是 None。
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT f.id, f.title, sc.name, c.name"
        " FROM files f"
        " LEFT JOIN courses sc ON sc.id = f.suggested_course_id"
        " LEFT JOIN courses c  ON c.id  = f.course_id"
        " ORDER BY f.id"
    ).fetchall()
    conn.close()
    return rows


def _get_or_create_tag(conn, name):
    """在**已经开好的连接**上按标签名查 id，没有就新建，返回 tag id。

    为什么不直接调下面那个 get_or_create_tag：那个会自己再开一条连接。
    SQLite 同一时刻只允许一条连接写库，set_file_tags 里正开着事务，
    再开一条去写同一张表就会报 "database is locked"。
    所以"在一段事务里反复查/建标签"要用这个版本。
    """
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return cur.lastrowid      # 刚插入那行的 id


def get_or_create_tag(name, db_path=_DB_PATH):
    """按标签名查标签 id；没有就新建一条。返回 tag id。（和 get_or_create_course 对称）"""
    conn = sqlite3.connect(db_path)
    tag_id = _get_or_create_tag(conn, name)
    conn.commit()
    conn.close()
    return tag_id


def list_tags(db_path=_DB_PATH):
    """返回所有标签 (id, name)，按名字排序。（和 list_courses 对称）"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, name FROM tags ORDER BY name").fetchall()
    conn.close()
    return rows


def list_file_tags(db_path=_DB_PATH):
    """
    返回所有「文件↔标签」关系 (文件id, 标签名, 来源, 状态)，按文件 id 排序。
    两个 LEFT JOIN 都不用（这里就是 INNER JOIN）：没关系就没行，正合适。
    界面拿它一次性拼出 {文件id: [(标签名, 来源, 状态), ...]}，只查一次库。
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT ft.file_id, t.name, ft.source, ft.status"
        " FROM file_tags ft JOIN tags t ON t.id = ft.tag_id"
        " ORDER BY ft.file_id"
    ).fetchall()
    conn.close()
    return rows


def set_file_tags(file_id, tag_names, db_path=_DB_PATH):
    """
    用户点「保存」时调用：把这个文件的标签对齐成 tag_names（用户最后看到的那份）。

    这是全项目唯一一处同时碰「三种标签状态」的地方，三种情况分开处理：
      · 选中的名字：没有这个标签就建；这个文件还没有它 → 新记一条 source='user'。
        已经有（比如自动标签，或者上次拒掉过的）→ **只把 status 改回 'active'，
        不动 source**——它是当初系统判的还是用户加的，要留痕（D-012）。
      · 原来有效、这次没选中的：source='auto' 的翻成 'rejected'（**行留着**，
        用户拒过什么是证据）；source='user' 的**整行删掉**——用户自己加的东西，
        他自己撤了，没有留痕价值。

    参数 tag_names：标签名字符串的列表，顺序无所谓，可以有重复和前后空格。
    """
    # 先洗干净：去空格、丢掉空串、去重，但保持用户看到的顺序（后面的逻辑按集合比）
    cleaned = []
    for name in tag_names:
        name = name.strip()
        if name and name not in cleaned:
            cleaned.append(name)

    conn = sqlite3.connect(db_path)

    # ① 选中的：没有就建标签，再按「这个文件有没有这个标签」分两种写法
    for name in cleaned:
        tag_id = _get_or_create_tag(conn, name)
        row = conn.execute(
            "SELECT status FROM file_tags WHERE file_id = ? AND tag_id = ?",
            (file_id, tag_id),
        ).fetchone()
        if row:
            # 已有这行：只翻回 active。注意不写 source——被拒过的自动标签
            # 应该继续标着 'auto'（是系统当初判的），只是用户现在又要了。
            conn.execute(
                "UPDATE file_tags SET status = 'active' WHERE file_id = ? AND tag_id = ?",
                (file_id, tag_id),
            )
        else:
            conn.execute(
                "INSERT INTO file_tags (file_id, tag_id, source, status)"
                " VALUES (?, ?, 'user', 'active')",
                (file_id, tag_id),
            )

    # ② 原来有效、这次没选中的：自动的留痕，用户加的删掉。
    #    查出来的就是"这个文件现在有效的全部标签"，在 Python 里跟 cleaned 逐个比，
    #    不写 SQL 的 NOT IN (...) —— 名字里的引号之类不用操心，判断也好读。
    for tag_id, name, source in conn.execute(
        "SELECT ft.tag_id, t.name, ft.source FROM file_tags ft JOIN tags t ON t.id = ft.tag_id"
        " WHERE ft.file_id = ? AND ft.status = 'active'",
        (file_id,),
    ).fetchall():
        if name in cleaned:
            continue                       # 这次还选着，不动
        if source == "auto":
            conn.execute(
                "UPDATE file_tags SET status = 'rejected' WHERE file_id = ? AND tag_id = ?",
                (file_id, tag_id),
            )
        else:
            conn.execute(
                "DELETE FROM file_tags WHERE file_id = ? AND tag_id = ?",
                (file_id, tag_id),
            )

    conn.commit()
    conn.close()


def add_auto_tag(file_id, tag_name, db_path=_DB_PATH):
    """记一条**系统自动**判出来的标签（导入时调）。

    **已经存在就什么都不做。** 具体说，靠 (file_id, tag_id) 这个复合主键加
    INSERT OR IGNORE 实现：命中已有行时 SQLite 直接跳过，既不会把它激活、
    也不会改它的 source。

    这一点是本轮最重要的不变量：doc_type 每次导入都会重算，如果这里用
    「重新对齐」的写法（先删后插、或者 INSERT OR REPLACE），用户在上次导入后
    **特意去掉**的自动标签，就会被下一次导入悄无声息地又装回去——而且没有任何
    提示。跟 _TOP_N、量具那几轮栽的是同一类错：改一处，另一处跟着动，没人发现。
    所以这里宁可"不做事"，也不"对了齐"。tests/test_tags.py 里专门钉了一条。
    """
    conn = sqlite3.connect(db_path)
    tag_id = _get_or_create_tag(conn, tag_name)
    conn.execute(
        "INSERT OR IGNORE INTO file_tags (file_id, tag_id, source, status)"
        " VALUES (?, ?, 'auto', 'active')",
        (file_id, tag_id),
    )
    conn.commit()
    conn.close()


def import_folder(folder, db_path=_DB_PATH):
    """扫描一个文件夹，把里面所有支持的文本文件导入数据库，返回导入数量。"""
    imported = 0  #导入数量
    for name in os.listdir(folder):
        if not name.endswith((".txt", ".md", ".pdf")):
            continue                     # 不支持的格式，跳过
        path = os.path.join(folder, name)   #拼出完整路径
        info = extract_file(path)                # 读取
        info["doc_type"] = classify_type(info["title"], info["text"])  # 分类
        course_name = suggest_course(name)       # 从文件名猜课程（猜不出返回 None）
        if course_name:
            info["suggested_course_id"] = get_or_create_course(course_name, db_path)
        file_id = save_file(info, db_path)       # 储存（返回这行的 id，下面挂标签要用）
        # 自动标签：把分类器判出来的类型也记一条。
        # 判成「未知」就不记——一个叫「未知」的标签是纯噪音，用户还得一个个去拒。
        # 注意 add_auto_tag 对**已经有过这条记录**的文件什么都不做，
        # 所以重复导入不会把用户拒掉的标签又装回去（见它的 docstring）。
        if info["doc_type"] and info["doc_type"] != "未知":
            add_auto_tag(file_id, info["doc_type"], db_path)
        imported += 1
    return imported


def search_files(keyword, db_path=_DB_PATH):
    """返回标题里包含 keyword 的所有文件 (id, path, title, 原因)。"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, path, title FROM files WHERE title LIKE ?",(f"%{keyword}%",)).fetchall()
    conn.close()
    # 每条结果附一句"为什么匹配"：标题含了这个关键词
    return [(fid, path, title, f"标题含「{keyword}」") for fid, path, title in rows]


def list_file_texts(db_path=_DB_PATH):
    """返回所有文件的 (id, title, text)，供正文关键词检索取正文用。"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, title, text FROM files").fetchall()
    conn.close()
    return rows


def list_file_vectors(model_name, db_path=_DB_PATH):
    """返回**已经用当前模型**算好向量的文件 (id, title, embedding)，供语义检索和聚类用。

    刻意不查 text：正文很大，而算余弦相似度只用得到向量。

    为什么必须按 model_name 过滤、而不是只查 `embedding IS NOT NULL`：
    不同模型的向量维度可能不一样（旧模型 768 维、新模型 512 维），拼到一起算余弦
    会直接崩（ValueError: Incompatible dimension）。而"库里混着两种模型"是真会发生的
    ——换模型要把全库重算一遍，几十秒的事，用户等不及 Ctrl-C 就中断了。
    口径和 list_files_needing_embedding 完全一致：只认「这行的模型名 == 当前模型名」。
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, title, embedding FROM files"
        " WHERE embedding IS NOT NULL AND embedding_model IS ?",
        (model_name,),
    ).fetchall()
    conn.close()
    return rows


def list_files_needing_embedding(model_name, db_path=_DB_PATH):
    """返回向量需要重算的文件 (id, text)。

    两种情况算「需要重算」：
      - embedding 是 NULL：还没算过，或者正文变了被 save_file 清空了；
      - embedding_model 和 model_name 对不上：模型换了，旧向量全不作数。
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, text FROM files"
        " WHERE embedding IS NULL OR embedding_model IS NOT ?",
        (model_name,),
    ).fetchall()
    conn.close()
    return rows


def save_embedding(file_id, embedding_blob, model_name, db_path=_DB_PATH):
    """把算好的向量写回这一行。

    参数 embedding_blob：向量转成的字节（numpy 数组的 .tobytes()）。
    参数 model_name：是哪个模型算的，将来靠它判断这行要不要重算。
    """
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE files SET embedding = ?, embedding_model = ? WHERE id = ?",
        (embedding_blob, model_name, file_id),
    )
    conn.commit()
    conn.close()


def save_chunks(file_id, chunks, db_path=_DB_PATH):
    """把切好的段落存进库（先把这个文件的旧段落全删掉，再按顺序重存一遍）。

    参数 chunks：chunk.chunk_text() 切出来的字符串列表，顺序就是原文顺序。
    """
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
    conn.executemany(
        "INSERT INTO chunks (file_id, seq, text) VALUES (?, ?, ?)",
        # seq 从 1 开始：这个号是给人看的「第几段」，从头读起来顺一点
        [(file_id, seq, text) for seq, text in enumerate(chunks, start=1)],
    )
    conn.commit()
    conn.close()


def list_files_without_chunks(db_path=_DB_PATH):
    """返回还没切过段的文件 (id, text)，供 index 切段入库。

    正文是空的（比如扫描件）就没有段落可切，直接跳过。
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, text FROM files"
        " WHERE id NOT IN (SELECT file_id FROM chunks)"
    ).fetchall()
    conn.close()
    # 空正文的判断放在 Python 里做，不要写成 SQL 的 trim(text) != ''——
    # SQLite 的 trim() 默认只去**空格**，不去换行和制表符，
    # 于是"只有几个换行"的正文会被当成有内容，每次都被拎出来重切一遍
    # （而重切又切不出任何段，永远轮不到它被标记成"切过了"）。
    # Python 的 str.strip() 去的才是全部空白字符。
    return [(file_id, text) for file_id, text in rows if text and text.strip()]


def list_chunks_needing_embedding(model_name, db_path=_DB_PATH):
    """返回向量需要重算的段落 (id, text)。

    判断和 list_files_needing_embedding 一模一样——段落向量和文档向量
    用同一个模型，过期规则自然也一样。
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, text FROM chunks"
        " WHERE embedding IS NULL OR embedding_model IS NOT ?",
        (model_name,),
    ).fetchall()
    conn.close()
    return rows


def save_chunk_embedding(chunk_id, embedding_blob, model_name, db_path=_DB_PATH):
    """把算好的段落向量写回这一行。"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE chunks SET embedding = ?, embedding_model = ? WHERE id = ?",
        (embedding_blob, model_name, chunk_id),
    )
    conn.commit()
    conn.close()


def list_chunk_vectors(model_name, db_path=_DB_PATH):
    """返回**已经用当前模型**算好向量的段落 (file_id, 文件标题, 段号, 段落正文, embedding)。

    要连文件标题一起取：检索结果最终是按「文件」呈现的，
    但得知道每一段属于哪个文件，才能把同文件的段落分数合成一个文件分。

    按 model_name 过滤的理由和 list_file_vectors 一模一样，见它的注释。
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT c.file_id, f.title, c.seq, c.text, c.embedding"
        " FROM chunks c JOIN files f ON f.id = c.file_id"
        " WHERE c.embedding IS NOT NULL AND c.embedding_model IS ?",
        (model_name,),
    ).fetchall()
    conn.close()
    return rows


def add_plan_item(action, files, reason, db_path=_DB_PATH):
    """往整理方案里加一条建议。"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO plan_items (action, files, reason) VALUES (?, ?, ?)",
        (action, files, reason),
    )
    conn.commit()
    conn.close()


def clear_plan_items(db_path=_DB_PATH):
    """清空整理方案（重新生成前先清掉旧的，避免重复）。"""
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM plan_items")
    conn.commit()
    conn.close()


def list_plan_items(db_path=_DB_PATH):
    """返回整理方案的所有建议 (id, action, files, reason, status)。"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, action, files, reason, status FROM plan_items").fetchall()
    conn.close()
    return rows


def set_plan_status(item_id, status, db_path=_DB_PATH):
    """把某条建议的状态改成 confirmed / rejected。"""
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE plan_items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()
    conn.close()



