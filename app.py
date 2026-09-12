import streamlit as st
from studyorganizer import store
from studyorganizer.search import search_semantic
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
        for _id, path, title in results:
            st.write(f"• {title}　（{path}）")
    else:
        st.warning("没有匹配的文件")

st.header("语义搜索")
sem_query = st.text_input("用自然语言描述要找的内容", placeholder="比如「讲过背包问题的资料」")
if sem_query:
    sem_results = search_semantic(sem_query)
    if sem_results:
        for title, score in sem_results:
            st.write(f"• {title}　（相关度 {score}）")
    else:
        st.warning("库里没有文件，先去左边导入")

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
