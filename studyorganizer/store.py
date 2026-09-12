"""store 模块：用 SQLite 把文件信息存起来。

SQLite 是"存在一个文件里的数据库"，Python 自带 sqlite3，不用额外安装。
数据存进 .db 文件后，程序关了也还在，还能用 SQL 查询。
"""

import os
import sqlite3
from studyorganizer.extract import extract_file
from studyorganizer.classify import classify_type

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
            is_scanned INTEGER DEFAULT 0
        )
    """)  #每行唯一一个编号,路径唯一,标题,正文,是否扫描件(默认0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS plan_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            files TEXT NOT NULL,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
        )
    """)  #整理方案：一行一条建议，files 存建议归并的文件标题
    conn.commit()  #保存
    conn.close()  #关闭


def save_file(info, db_path=_DB_PATH):
    """
    把 extract_file 返回的字典存进数据库。
    info 里要有：path、title、text（is_scanned 可选，默认 False）
    """
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO files (path, title, doc_type, text, is_scanned) VALUES (?, ?, ?, ?, ?)",
        (info["path"], info["title"], info.get("doc_type"), info["text"], 1 if info.get("is_scanned") else 0),
    )
    conn.commit()
    conn.close()


def list_files(db_path=_DB_PATH):
    """返回数据库里所有文件的 (id, path, title, doc_type)。"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, path, title, doc_type FROM files").fetchall()
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
        save_file(info, db_path)                 # 储存
        imported += 1
    return imported


def search_files(keyword, db_path=_DB_PATH):
    """返回标题里包含 keyword 的所有文件 (id, path, title)。"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, path, title FROM files WHERE title LIKE ?",(f"%{keyword}%",)).fetchall()
    conn.close()
    return rows


def list_file_texts(db_path=_DB_PATH):
    """返回所有文件的 (id, title, text)，供语义检索取正文用。"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, title, text FROM files").fetchall()
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



