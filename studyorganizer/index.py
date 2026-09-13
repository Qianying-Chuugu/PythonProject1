"""index 模块：确保数据库里的向量是最新的。

向量很贵——算一遍要过模型。所以算完就存进库里，之后直接用。
这个模块只回答一个问题：「哪些行的向量已经不算数了？」

库里存着两种向量，各有一套「建好」的函数：
  - `files.embedding`  文档级，聚类用   → ensure_embeddings()
  - `chunks.embedding` 段落级，检索用   → ensure_chunk_embeddings()

两种的过期规则完全一样，都是这三种情况收敛成同一个判断：
  1. 还没有向量   → embedding 是 NULL
  2. 模型换了     → embedding_model 和当前模型名对不上
  3. 文件内容变了 → save_file 会主动把 embedding 清空（见 store.py），
                    段落那边还会把旧段落整批删掉等着重切

好处是「模型换了」不需要写任何特殊代码：所有行都不满足条件，自然全部重算。

依赖方向：index → store, search, chunk。
store / search / chunk 都不依赖 index，所以不会循环导入；也正因为如此，
建索引只能从这里或界面层触发，search 内部不能反过来调这里。
"""

from studyorganizer import store
from studyorganizer.chunk import chunk_text
from studyorganizer.search import MODEL_NAME, get_model


def ensure_embeddings(db_path=store._DB_PATH):
    """把库里过期的向量补算上，返回这次算了几条。

    幂等：没有过期的就什么都不做，也不会重复算。
    """
    rows = store.list_files_needing_embedding(MODEL_NAME, db_path)
    if not rows:
        return 0

    file_ids = [r[0] for r in rows]
    texts = [r[1] for r in rows]

    # 一次把所有正文喂给模型（批量），比在循环里一条一条算快得多
    vectors = get_model().encode(texts)
    for file_id, vector in zip(file_ids, vectors):
        store.save_embedding(file_id, vector.tobytes(), MODEL_NAME, db_path)

    return len(file_ids)


def ensure_chunk_embeddings(db_path=store._DB_PATH):
    """把该切的段切好、过期的段落向量补算上。返回 (切了几篇, 算了几段)。

    和 ensure_embeddings 是一对：那个管「文档级向量」（聚类用），
    这个管「段落级向量」（语义检索用）。两边都幂等。

    分两步，顺序不能反：
      1. 还没切过段的文件 → 调 chunk.chunk_text() 切好入库；
      2. 段落里向量过期或还没算的 → 一次性喂给模型，写回库里。
    """
    # ① 切段：正文是空的（扫描件）在上面就被过滤掉了，切不出段也没关系
    pending = store.list_files_without_chunks(db_path)
    for file_id, text in pending:
        store.save_chunks(file_id, chunk_text(text), db_path)

    # ② 算向量
    rows = store.list_chunks_needing_embedding(MODEL_NAME, db_path)
    if not rows:
        return len(pending), 0

    chunk_ids = [r[0] for r in rows]
    texts = [r[1] for r in rows]

    # 一次全喂给模型（批量），比一条一条算快得多
    vectors = get_model().encode(texts)
    for chunk_id, vector in zip(chunk_ids, vectors):
        store.save_chunk_embedding(chunk_id, vector.tobytes(), MODEL_NAME, db_path)

    return len(pending), len(chunk_ids)


def import_and_index(folder, db_path=store._DB_PATH):
    """导入一个文件夹并建好索引，返回导入的文件数。

    界面应该用这个，而不是直接用 store.import_folder——
    否则新导入的文件没有向量，语义检索会找不到它们。
    """
    store.init_db(db_path)
    n = store.import_folder(folder, db_path)
    ensure_embeddings(db_path)          # 文档级向量（聚类用）
    ensure_chunk_embeddings(db_path)    # 段落级向量（语义检索用）
    return n
