import streamlit as st
from studyorganizer import store
from studyorganizer.search import search_semantic, search_keyword, search_hybrid
from studyorganizer.plan import generate_plan, export_report

st.title("📚 StudyOrganizer 课程资料整理")

# ---- 侧边栏：导入资料 ----
with st.sidebar:
    st.header("导入资料")
    folder = st.text_input("文件夹路径", "practice")
    if st.button("导入"):
        store.init_db()
        n = store.import_folder(folder)
        st.success(f"导入了 {n} 个文件")

# ---- 主区 ----
store.init_db()   # 确保表存在（第一次运行会建表）

st.header("文件库")
rows = store.list_files()          # [(id, path, title, doc_type), ...]
if rows:
    st.write(f"共 {len(rows)} 个文件")
    st.dataframe([
        {"标题": title, "类型": doc_type or "—", "路径": path}
        for _id, path, title, doc_type in rows
    ])
else:
    st.info("库里还没有文件，去左边导入一个文件夹")

st.header("搜索")
keyword = st.text_input("按标题关键词搜", placeholder="比如「讲义」")
if keyword:
    results = store.search_files(keyword)
    if results:
        for _id, path, title, reason in results:
            st.write(f"• {title}　—— {reason}　（{path}）")
    else:
        st.warning("没有匹配的文件")

st.header("正文关键词搜索")
kw_query = st.text_input("按正文关键词搜（TF-IDF）", placeholder="比如「动态规划」")
if kw_query:
    kw_results = search_keyword(kw_query)
    if kw_results:
        for title, _score, reason in kw_results:
            st.write(f"• {title}　—— {reason}")
    elif not rows:          # 结果为空有两种原因，分开提示
        st.warning("库里没有文件，先去左边导入")
    else:
        st.warning("没有匹配的文件")

st.header("语义搜索")
sem_query = st.text_input("用自然语言描述要找的内容", placeholder="比如「讲过背包问题的资料」")
if sem_query:
    sem_results = search_semantic(sem_query)
    if sem_results:
        for title, _score, reason in sem_results:   # _score 用不上（相似度已含在 reason 里）
            st.write(f"• {title}　—— {reason}")
    elif not rows:          # 结果为空有两种原因，分开提示
        st.warning("库里没有文件，先去左边导入")
    else:
        st.warning("没有匹配的文件")

st.header("混合检索（三种方法加权）")
hyb_query = st.text_input("输入搜索内容，看三种方法综合的结果", placeholder="比如「动态规划」")
if hyb_query:
    hyb_results = search_hybrid(hyb_query)
    if hyb_results:
        for title, score, reason in hyb_results:
            st.write(f"• {title}　总分 {score}")
            st.caption(f"原因：{reason}")      # 原因可能有好几条，独占一行更清楚
    elif not rows:
        st.warning("库里没有文件，先去左边导入")
    else:
        st.warning("没有匹配的文件")

st.header("整理方案")

if st.button("生成整理方案"):
    plan = generate_plan()
    st.success(f"生成了 {len(plan)} 条建议")
    st.session_state["show_plan"] = True      # 记住"本会话点过生成"

if st.session_state.get("show_plan"):          # 只有点过生成才显示
    items = store.list_plan_items()
    if items:
        for item_id, action, files, reason, status in items:
            st.markdown(f"**{action}**（{status}）：{files}")
            st.caption(reason)
            if status == "pending":
                c1, c2 = st.columns(2)
                if c1.button("✓ 确认", key=f"ok_{item_id}"):
                    store.set_plan_status(item_id, "confirmed")
                    st.rerun()
                if c2.button("✗ 拒绝", key=f"no_{item_id}"):
                    store.set_plan_status(item_id, "rejected")
                    st.rerun()
            st.divider()
        if st.button("📄 导出整理报告"):
            n = export_report()
            if n:
                st.success(f"已导出 {n} 条建议到「整理方案.md」")
            else:
                st.warning("还没有已确认的建议，先点「确认」")
    else:
        st.info("还没有整理方案")
