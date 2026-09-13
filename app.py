import streamlit as st
from studyorganizer import index, store
from studyorganizer.search import MODEL_NAME, search_semantic, search_keyword, search_hybrid
from studyorganizer.plan import generate_plan, export_report

st.title("📚 StudyOrganizer 课程资料整理")

# ---- 侧边栏：导入资料 ----
with st.sidebar:
    st.header("导入资料")
    folder = st.text_input("文件夹路径", "practice")
    if st.button("导入"):
        # 用 index 的入口，不用 store.import_folder——导入完顺手把向量也建好，
        # 否则新导入的文件没有向量，语义检索会漏掉它们。
        n = index.import_and_index(folder)
        st.success(f"导入了 {n} 个文件（已建好索引）")

# ---- 主区 ----
store.init_db()   # 确保表存在（第一次运行会建表）

# 启动时补一次索引：老库（这次改动之前导入的文件没有向量）靠这一步自动补上。
# 没有过期的就什么都不做，也不会下载模型（库是空的 / 向量都在 → 直接返回）。
with st.spinner("检查索引…"):
    _n_doc = index.ensure_embeddings()                  # 文档级向量（聚类用）
    _n_cut, _n_chunk = index.ensure_chunk_embeddings()  # 段落级向量（检索用）
if _n_doc or _n_cut or _n_chunk:
    st.info(f"补建索引：文档向量 {_n_doc} 个；{_n_cut} 篇文件切出 {_n_chunk} 段并算好向量")

# 标签数据在这里读**一次**，下面「文件库」的筛选和「标签」区都用它。
# app.py 是平铺脚本、从上往下执行，顺序就是依赖关系——所以这块必须写在
# 用到它的那两段**前面**，不能等到「标签」区再查。
tags_by_file = {}      # {文件id: [(标签名, 来源, 状态), ...]}
active_tags = set()    # 正在用的标签名（下面当筛选和编辑的选项用）
for _fid, _name, _source, _status in store.list_file_tags():
    tags_by_file.setdefault(_fid, []).append((_name, _source, _status))
    if _status == "active":
        active_tags.add(_name)
active_tags = sorted(active_tags)

st.header("文件库")
rows = store.list_files()          # [(id, path, title, doc_type), ...]
if rows:
    # 按标签筛选：勾中**任意一个**就显示（并集）。这是"浏览"的用法——
    # 想同时看两门课的讲义时，两个都勾上比让用户去理解"与/或"顺得多。
    # 一个正在用的标签都没有就不渲染这个控件，免得上边挂个空框。
    picked_tags = st.multiselect("按标签筛选", active_tags, key="filter_tags") if active_tags else []

    table = []
    for fid, path, title, doc_type in rows:
        mine = [name for name, _src, status in tags_by_file.get(fid, []) if status == "active"]
        if picked_tags and not set(mine) & set(picked_tags):
            continue                   # 勾了标签，这个文件一个都不沾 → 不显示
        table.append({
            "标题": title, "类型": doc_type or "—",
            "标签": "、".join(mine) or "—", "路径": path,
        })

    if picked_tags:
        st.write(f"共 {len(table)} 个文件（按标签筛掉 {len(rows) - len(table)} 个）")
    else:
        st.write(f"共 {len(table)} 个文件")
    if table:
        st.dataframe(table)
    else:
        st.info("没有文件带这些标签")
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

st.header("语义搜索（按段落匹配）")
sem_query = st.text_input("用自然语言描述要找的内容", placeholder="比如「背包问题的状态转移方程怎么写的」")
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

st.header("课程归属")

file_courses = store.list_files_with_course()   # [(id, 标题, 建议课程, 已确认课程), ...]
courses = store.list_courses()                  # [(id, 课程名), ...]
name_to_id = {name: cid for cid, name in courses}   # 课程名 → id 的对照表
_UNSET = "（未指定）"
options = [_UNSET] + list(name_to_id)           # 下拉框选项

if not courses:
    st.info("还没有课程，先去左边导入资料（导入时会自动猜课程）")
else:
    for fid, title, suggested, confirmed in file_courses:
        c1, c2, c3 = st.columns([4, 3, 1])
        c1.write(f"**{title}**")
        if confirmed:
            c2.write(f"✓ 已确认：{confirmed}")        # 确认过的不再给下拉框
        else:
            default = suggested if suggested in name_to_id else _UNSET
            picked = c2.selectbox(
                f"课程_{fid}", options,
                index=options.index(default),          # 默认选中系统建议的课程
                key=f"pick_{fid}", label_visibility="collapsed",
            )
            # key 必须带 course_ 前缀：「整理方案」的确认按钮也叫 ok_{id}，
            # 而**文件 id 和方案条目 id 是两套独立的数字，都从 1 开始**
            # ——只要有份还没确认课程的文件，id 撞上某条 pending 方案条目，
            # Streamlit 当场报 StreamlitDuplicateElementKey（ok_1 撞 ok_1），
            # 两块内容一起渲染不出来。加前缀是为了把两个命名空间分开。
            if c3.button("确认", key=f"course_ok_{fid}"):
                if picked == _UNSET:
                    st.warning("请先选一门课")
                else:
                    store.set_file_course(fid, name_to_id[picked])
                    st.rerun()

st.header("标签")

if not rows:
    st.info("库里还没有文件，去左边导入一个文件夹")
else:
    st.caption("导入时按文件类型自动打了标签；在这里可以改，也可以自己加新的。")
    for fid, _path, title, _doc_type in rows:
        entries = tags_by_file.get(fid, [])          # [(标签名, 来源, 状态), ...]
        mine = [name for name, _src, status in entries if status == "active"]   # 现在有效的
        rejected = [name for name, _src, status in entries if status == "rejected"]  # 拒过的

        c1, c2, c3 = st.columns([4, 5, 1])
        c1.write(f"**{title}**")
        # 跟上面「课程归属」不一样：这里**不做"确认过就把控件收起来"**。
        # 课程是单选，定了就定了；标签是多值的、要能反复改，每次都得重新点开一遍
        # 反而更烦。这是有意偏离课程区，不是漏写。
        # 下面是本仓库第一个 st.multiselect。
        # accept_new_options=True（Streamlit 1.45+）让用户能直接手输新标签，
        # 不用再多放一个输入框。
        # key 前缀用 tags_ / save_tag_，是特意跟「整理方案」的 ok_/no_ 错开的
        # ——文件 id 和方案条目 id 是两套独立的数字，都从 1 开始，会撞车。
        picked = c2.multiselect(
            f"标签_{fid}", active_tags, default=mine,
            key=f"tags_{fid}", accept_new_options=True,
            label_visibility="collapsed",
        )
        if c3.button("保存", key=f"save_tag_{fid}"):
            store.set_file_tags(fid, picked)
            st.rerun()
        if rejected:
            # 拒过的自动标签得看得见。不然用户拒完就再也想不起来拒过什么，
            # 也没法确认"重新导入会不会又冒出来"（不会，见 store.add_auto_tag）。
            st.caption(f"已忽略的自动标签：{'、'.join(rejected)}")

st.header("整理方案")

if st.button("生成整理方案"):
    plan = generate_plan(MODEL_NAME)
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
