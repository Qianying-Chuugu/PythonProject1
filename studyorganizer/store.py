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
    """
    conn = sqlite3.connect(db_path)
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
    conn.commit()
    conn.close()


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
        save_file(info, db_path)                 # 储存
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


def list_file_vectors(db_path=_DB_PATH):
    """返回已经有向量的文件 (id, title, embedding)，供语义检索和聚类用。

    刻意不查 text：正文很大，而算余弦相似度只用得到向量。
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, title, embedding FROM files WHERE embedding IS NOT NULL"
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



