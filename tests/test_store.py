import os
from studyorganizer import store

# 用单独的测试库，不污染真正的 studyorganizer.db
TEST_DB = "test_store.db"


def test_存取和查询():
    # 清理上一次测试留下的库
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    store.init_db(TEST_DB)
    store.save_file({"path": "a.txt", "title": "动态规划讲义", "text": "状态转移"}, TEST_DB)
    store.save_file({"path": "b.txt", "title": "英语笔记", "text": "单词"}, TEST_DB)

    # 存了 2 个，列出来应该有 2 个
    assert len(store.list_files(TEST_DB)) == 2

    # 按标题搜"动态"应该只找到 1 个，且标题对
    results = store.search_files("动态", TEST_DB)
    assert len(results) == 1
    assert results[0][2] == "动态规划讲义"
