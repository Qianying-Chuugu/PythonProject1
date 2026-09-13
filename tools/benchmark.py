"""tools/benchmark.py —— 检索实测脚本（手动跑，不进 pytest）

为什么要有这个脚本
------------------
DESIGN.md 里那张「模型对照表」（放行率 / 间距 / 编码耗时 / 体积）是实测出来的，
但当时用的是一次性脚本，跑完就删了。结果是那些数字**谁也复现不了**：
practice/ 里加几个文件，表里的数就悄悄过期，而且没有任何东西会提醒你。
这个脚本把它固定下来，随时能重跑。

怎么用
------
    python tools/benchmark.py                                  # 测当前模型
    python tools/benchmark.py --check                          # 回归检查（有答案没排第 1 就非 0 退出）
    python tools/benchmark.py --model BAAI/bge-base-zh-v1.5     # 换模型对比
    python tools/benchmark.py --corpus practice                 # 换语料

它会
----
  1. 用一个**临时数据库**（绝不碰你仓库里的 studyorganizer.db）；
  2. 走真正的生产路径建库：index.import_and_index()；
  3. 每条测试查询看「正确答案排第几」——调的是真的 search.search_semantic()；
  4. 再做段落级间距和阈值扫描；
  5. 打印一份报告。

**改完检索代码，跑 `--check` 那行。**不加 `--check` 时脚本只报告、不判定；
加上之后，只要有一条查询的标准答案没排在第一位就以非 0 退出，可以拿去卡回归。

标准答案怎么定的
----------------
见下面 QUERIES 里每条的 note。**每条都是打开文件读过之后定的**，不是看文件名猜的
——NOTES.md 第 8 条记着这个教训：当时凭文件名标错答案，差点得出「模型分不清」的
错误结论，真正错的是标注本身。

Windows 控制台如果显示乱码
--------------------------
    PYTHONIOENCODING=utf-8 python tools/benchmark.py > report.txt
再打开 report.txt 看。
"""

import argparse
import inspect
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# 让 `python tools/benchmark.py` 能 import 到 studyorganizer/
# （直接跑脚本时，sys.path[0] 是 tools/ 而不是仓库根目录）
_仓库根 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_仓库根))
# 控制台编码不认识的字符（比如各种符号）直接替换掉，别让打印把整个脚本搞崩
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):    # 输出被重定向到某些不是标准流的东西时
    pass

from studyorganizer import index, search, store


# ========================================================================
# 测试查询和标准答案
#
# 加查询时的规矩：**打开文件读一遍再填 answers**，不要凭文件名猜。
# answers 可以列多个（一道题的内容散在几个文件里是常态）；
# 只列「真的答了这个问题」的文件——只是沾边、或者只是提出问题的，不算。
# 每条 note 末尾标了**难度**：低 = 语料里只有一个文件沾边，基本是送分；
# 中/高 = 有干扰文件来抢位置，才真正在量区分度。全低分不代表检索好。
# ========================================================================
QUERIES = [
    # ---------- 算法：动态规划（语料里最难的一块——5 个文件都在讲 DP）----------
    {
        "q": "0-1 背包问题的状态转移方程是什么",
        # 只有长讲义写了完整方程（第 23 段）：
        #   dp[i][j] = max(dp[i-1][j], dp[i-1][j-w[i]] + v[i])
        "answers": ["算法_动态规划长讲义.txt"],
        "note": "讲义1.txt 只给了状态定义、没给方程；作业1.txt 是题目本身（只提示"
                "倒序/正序枚举）；笔记2.md 只把背包列为题型。都不算答案——标严一点，"
                "名次才有意义。**难度：高**（4 个 DP 文件都在抢这个位置）",
    },
    {
        "q": "最长递增子序列的长度怎么求",
        "answers": ["算法_动态规划长讲义.txt"],
        "note": "长讲义第 27 段专讲 LIS（O(n²) 和 O(n log n) 两种做法）。笔记2.md 的"
                "题型清单里也有「最长递增子序列」这个词，但没给做法，不算。"
                "**难度：中**（笔记2 的题型清单是干扰项）。",
    },
    {
        "q": "动态规划的状态应该怎么定义",
        # 四个文件都实质讲了状态定义，不是沾边：
        #   长讲义第 11 段专门讲「状态定义最重要也最容易做错」+ 检验方法
        #   笔记1.txt「重点：状态的定义和状态转移方程」「先想清楚状态表示什么」
        #   笔记2.md「1. 定义状态：明确 dp 数组的含义」
        #   讲义1.txt「1. 定义状态：明确 dp 数组每个元素表示什么」
        "answers": [
            "算法_动态规划长讲义.txt",
            "笔记1.txt",
            "笔记2.md",
            "讲义1.txt",
        ],
        "note": "**这条就是 NOTES.md 第 8 条里我标错过的那条。** 当时只填了长讲义，"
                "结果另外三个文件排在前面，我以为是模型分不清——其实是它们才是更贴题的"
                "答案，是我漏标了。现在四个都填上。**难度：低**（答案多）。",
    },
    {
        "q": "动态规划和贪心有什么区别",
        # 三处都明写「贪心只看当前最优，动态规划考虑全局最优」
        "answers": [
            "算法_动态规划长讲义.txt",
            "笔记1.txt",
            "讲义1.txt",
        ],
        "note": "笔记2.md 完全没提贪心，所以不算。**难度：低**。",
    },
    {
        "q": "Dijkstra 和 Floyd 算法有什么区别",
        "answers": ["算法_图论最短路径.txt"],
        "note": "只有这篇讲最短路，两个算法都写了（Dijkstra 非负权贪心 / Floyd 动态"
                "规划求全点对）。**难度：中**——Floyd 也是动态规划，DP 那几篇有被误召回"
                "的可能。",
    },
    # ---------- 操作系统 ----------
    {
        "q": "时间片轮转是怎么调度的",
        "answers": ["操作系统_进程调度长讲义.pdf", "操作系统_进程调度.txt"],
        "note": "长讲义第 5、6 段详述（含时间片长短的取舍、一般取 10~100 毫秒）；"
                "短讲义只有一句定义。两个都算答案。**难度：中**。",
    },
    {
        "q": "死锁产生的四个必要条件是什么",
        "answers": ["操作系统_进程调度.txt"],
        "note": "只有短讲义写了这四个（互斥、占有且等待、不可剥夺、循环等待）——"
                "长讲义通篇讲调度，没提死锁。**难度：中**（两份 OS 文件容易互相干扰，"
                "长讲义很大、段落多，靠蒙中高分的机会也多）。",
    },
    # ---------- 其余的按科目铺开，保证覆盖面 ----------
    {
        "q": "过拟合怎么解决",
        # 「解决方法：正则化（L1/L2）、增加训练数据、早停、dropout、数据增强」
        "answers": ["机器学习_梯度下降讲义.md"],
        "note": "深度学习笔记里也出现了「数据增强防止过拟合」，但没讲怎么解决过拟合"
                "本身，不算。**难度：中**——旧模型就是栽在这条上（正确答案掉到第 4，"
                "前面全是不相关的文件）。",
    },
    {
        "q": "神经网络的激活函数有哪些",
        "answers": ["深度学习_神经网络笔记.md"],
        "note": "列了 Sigmoid / ReLU / Softmax 并说明各自特点。**难度：低**。",
    },
    {
        "q": "Cache 是怎么利用局部性原理的",
        "answers": ["计算机组成原理_存储体系.txt"],
        "note": "写了时间局部性和空间局部性，并明说「Cache 正是利用局部性原理」。"
                "**难度：低**。",
    },
    {
        "q": "TCP 为什么是三次握手而不是两次",
        "answers": ["计算机网络_TCP笔记.md"],
        "note": "明写「为了防止已失效的连接请求突然又传到服务器」。**难度：低**。",
    },
    {
        "q": "数据库的三大范式分别是什么",
        "answers": ["数据库_SQL作业.txt"],
        "note": "1NF / 2NF / 3NF 都给了定义（这份作业把答案也写上了）。注意同一份文件"
                "里还有几道只有题目、没答案的 SQL 题。**难度：低**。",
    },
    {
        "q": "栈和队列有什么区别",
        "answers": ["数据结构_栈与队列.txt"],
        "note": "写了 LIFO / FIFO、各自的操作和应用场景。图论讲义里有「DFS 用栈、BFS "
                "用队列」，但那是遍历的实现方式、没讲两者的区别，不算。**难度：中**。",
    },
    {
        "q": "德摩根定律是什么",
        "answers": ["离散数学_命题逻辑讲义.txt"],
        "note": "两条都写了（¬(A∧B) ≡ ¬A∨¬B，¬(A∨B) ≡ ¬A∧¬B）。**难度：低**。",
    },
    {
        "q": "需求获取有哪些方法",
        "answers": ["软件工程_需求分析讲义.txt"],
        "note": "访谈 / 问卷调查 / 观察法 / 原型法四种。**难度：低**。",
    },
    {
        "q": "酸碱中和滴定的实验步骤是什么",
        "answers": ["化学_酸碱滴定实验报告.txt"],
        "note": "四步都写了（润洗滴定管、量取待测液加酚酞、滴到刚好褪色、重复取平均）。"
                "**难度：低**。",
    },
    {
        "q": "欧姆定律实验是怎么验证的",
        "answers": ["物理_欧姆定律实验报告.txt"],
        "note": "伏安法、改变滑动变阻器取多组数据、画 U-I 图像看是否过原点。"
                "**难度：低**。",
    },
    # ---------- 只有题目、没有答案的试卷 / 作业 ----------
    # 这几份是"试卷/作业"类型，内容本身就是题目。标准答案填它们，
    # 意思是"该被检索到的是这份卷子"，不是"它答了这个问题"。
    # 它们文字少、又跟别的科目不像，正好用来看"薄内容"能不能被找到。
    {
        "q": "作文的开头段怎么写",
        "answers": ["英语_四六级作文笔记.md"],
        "note": "给了开头段模板（With the development of society...）和首尾段的结构。"
                "**难度：低**。",
    },
    {
        "q": "最大似然估计怎么估计参数",
        "answers": ["概率论_期末试卷.txt"],
        "note": "**这份是试卷，只写了题、没写答案**——所以这里的意思是「该被找到的是"
                "这张卷子」，不是「它答了这个问题」。它是语料里唯一涉及最大似然估计的"
                "文件。**难度：低**。",
    },
    {
        "q": "矩阵的特征值和特征向量怎么求",
        "answers": ["线性代数_期末试卷.txt"],
        "note": "同上：只有题目（求特征值、判断可否对角化）。语料里唯一的线性代数文件。"
                "**难度：低**。",
    },
    {
        "q": "判断级数收敛性的方法",
        "answers": ["高等数学_微积分作业.txt"],
        "note": "同上：只有题目（调和级数、∑1/n² 是否收敛）。语料里唯一的高数文件。"
                "**难度：低**。",
    },
]


# 当前默认的相似度下限。**从 search_semantic 的签名里读，不要在这里另抄一份。**
# 抄一份的后果是：哪天把 search.py 的默认值改了，这个脚本还会印着旧的数说
# 「<- 当前默认」，报告本身就变成假的——量具的错，跟 NOTES.md 第 10 条同一类。
当前默认阈值 = inspect.signature(search.search_semantic).parameters["min_score"].default

# 阈值扫描用哪几个数。当前默认那个一定在里面（下面塞进去），方便一眼看它落在哪。
THRESHOLDS = sorted({0.30, 0.40, 0.50, 0.55, 0.60, 0.65, 0.70, 当前默认阈值})


# ------------------------------------------------------------------------
# 小工具
# ------------------------------------------------------------------------

def _模型体积():
    """从 HuggingFace 缓存目录量出模型占了多大硬盘。量不到就返回 None。

    量的是**整个模型目录**，同一个仓库的多个 revision 都算——因为在硬盘上它们
    确实各占一份（bge-base 就存了两个 revision，加起来 781 MB）。这和 DESIGN.md
    里那张表的「体积」是同一个口径。

    但如果缓存是另一种布局（blobs/ 里放真文件、snapshots/ 里是符号链接），
    按整个目录量会把同一份权重算两遍，所以那种情况下只量 blobs/。
    """
    for 家 in [
        os.environ.get("HF_HOME"),
        Path.home() / ".cache" / "huggingface",
        Path.home() / ".cache" / "torch" / "sentence_transformers",
    ]:
        if not 家:
            continue
        根 = Path(家) / "hub" / ("models--" + search.MODEL_NAME.replace("/", "--"))
        if not 根.exists():
            continue
        blobs = 根 / "blobs"
        blobs里有 = [f for f in blobs.rglob("*") if f.is_file()] if blobs.exists() else []
        量的地方 = blobs if blobs里有 else 根
        字节 = sum(f.stat().st_size for f in 量的地方.rglob("*") if f.is_file())
        if 字节:
            return 字节
    return None


def _排第几(results, answers):
    """正确答案在结果列表里排第几（1 开始）；没上榜返回 None。"""
    for 名次, (标题, _分, _原因) in enumerate(results, start=1):
        if 标题 in answers:
            return 名次
    return None


# ------------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------------

def 跑一次(args):
    语料 = (_仓库根 / args.corpus).resolve()
    if not 语料.is_dir():
        print(f"找不到语料目录：{语料}")
        return 1

    # 换模型的话，三个地方都得改：
    #   search.MODEL_NAME —— get_model() 和读向量时用它
    #   index.MODEL_NAME  —— index.py 是 `from ... import MODEL_NAME`，
    #                        导入时就绑死了，是**另一份**，改 search 那份它不跟着变
    #   search._model     —— 可能已经缓存了上一个模型，得丢掉
    if args.model != search.MODEL_NAME:
        search.MODEL_NAME = args.model
        index.MODEL_NAME = args.model
        search._model = None

    print("=" * 72)
    print("StudyOrganizer 检索实测")
    print("=" * 72)

    with tempfile.TemporaryDirectory() as 临时目录:
        # store.py 里的 _DB_PATH 是**相对**路径 "studyorganizer.db"，
        # 所有函数的默认参数都是它，最终由当前工作目录决定落在哪。
        # 所以只要把工作目录切到临时目录，默认参数就自动指向临时库了——
        # 不用 monkeypatch 任何东西，search_semantic 走的还是原样代码。
        # （这也是 DESIGN.md「一个已知的接口不整齐处」说的问题：函数不收 db_path。）
        原目录 = os.getcwd()
        os.chdir(临时目录)
        try:
            return _测量(args, 语料)
        finally:
            os.chdir(原目录)


def _测量(args, 语料):
    print(f"\n模型：{search.MODEL_NAME}")
    print(f"语料：{args.corpus}/")

    # 先把模型加载好，别把"加载模型"的时间算进下面的"建库"
    # （不然建库耗时会虚高十几秒，换模型对比时这个数就没意义了）
    model = search.get_model()

    # ---- 建库（真正的生产路径：导入 → 切段 → 算向量）----
    t0 = time.perf_counter()
    文件数 = index.import_and_index(str(语料))
    建库秒 = time.perf_counter() - t0

    rows = store.list_chunk_vectors(search.MODEL_NAME)
    if not rows:
        print("临时库里一段都没切出来，检查语料目录。")
        return 1

    标题表 = [r[1] for r in rows]
    段落正文 = [r[3] for r in rows]
    段落向量 = np.vstack([np.frombuffer(r[4], dtype=np.float32) for r in rows])

    # 新版 sentence-transformers 改过名，旧的会报 FutureWarning
    _取维度 = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
    维度 = _取维度()

    # 单独量一次编码耗时：模型已经加载好了，这里量的是纯编码
    t0 = time.perf_counter()
    model.encode(段落正文)
    编码秒 = time.perf_counter() - t0

    体积 = _模型体积()

    print(f"规模：{文件数} 个文件 / {len(rows)} 段")
    print(f"向量：{维度} 维")
    print(f"建库总耗时（导入 + 切段 + 编码，不含加载模型）：{建库秒:.1f}s")
    print(f"其中纯编码 {len(rows)} 段：{编码秒:.1f}s")
    if 体积:
        print(f"模型体积（缓存里占的硬盘）：{体积 / 1024 / 1024:.0f} MB")
    else:
        print("模型体积：量不到（缓存目录没找到，不影响其它指标）")

    # ---- 把标准答案（文件名）翻成标题 ----
    # search_semantic 返回的是**清洗过的标题**，不是文件名：extract 会把下划线换成
    # 空格、去掉扩展名（`算法_动态规划长讲义.txt` → `算法 动态规划长讲义`）。
    # 标准答案里写文件名是因为它好认、跟磁盘上对得上，所以这里要翻译一道。
    # 踩过的坑：一开始直接拿文件名去比，结果 6 条查询全部"未上榜"，
    # 而 top-1 明明就是正确答案——**错的是量具，不是被测的东西**（NOTES.md 第 10 条）。
    文件名到标题 = {}
    for _fid, 路径, 标题, _类型 in store.list_files():
        文件名到标题[os.path.basename(路径)] = 标题

    撞名 = {}
    for 标题 in 文件名到标题.values():
        撞名[标题] = 撞名.get(标题, 0) + 1
    有撞名 = sorted(t for t, n in 撞名.items() if n > 1)

    答案标题 = {}
    对不上 = []
    for 用例 in QUERIES:
        名字们 = 用例["answers"]
        缺 = [n for n in 名字们 if n not in 文件名到标题]
        if 缺:
            对不上.extend(缺)
            continue
        答案标题[用例["q"]] = {文件名到标题[n] for n in 名字们}

    if 对不上:
        print("\n!! 标准答案里有对不上的文件名（语料里没有，或者名字写错了）：")
        for 名字 in 对不上:
            print(f"   - {名字}")
        return 1
    if 有撞名:
        print(f"\n!! 警告：这些标题被多个文件共用，按标题找答案会串台：{有撞名}")

    # 答案是按查询句子作键查的，两条一样的查询会互相覆盖——这种错会静默发生，
    # 所以宁可当场停下来（NOTES.md 第 10 条讲的正是"别让它静默"）
    问句计数 = {}
    for 用例 in QUERIES:
        问句计数[用例["q"]] = 问句计数.get(用例["q"], 0) + 1
    重复问句 = sorted(q for q, n in 问句计数.items() if n > 1)
    if 重复问句:
        print(f"\n!! QUERIES 里有重复的查询（后面的会顶掉前面的答案）：{重复问句}")
        return 1

    # ---- ① 每条查询：正确答案排第几 ----
    print("\n" + "=" * 72)
    print("一、每条查询：正确答案排第几")
    print("=" * 72)
    print("调的是真的 search.search_semantic()，就是界面上会发生的事。")
    print("名次 1 = 最好；「未上榜」= 分数全被 min_score 砍掉了。\n")

    排名汇总 = []
    for i, 用例 in enumerate(QUERIES, start=1):
        这条的答案 = 答案标题[用例["q"]]
        结果 = search.search_semantic(用例["q"], top_k=999)
        名次 = _排第几(结果, 这条的答案)
        排名汇总.append(名次)

        print(f"[{i}] {用例['q']}")
        print(f"    标准答案（文件）：{'、'.join(用例['answers'])}")
        打印标题 = [f"{n} → 「{文件名到标题[n]}」" for n in 用例["answers"]
                    if 文件名到标题[n] != n]
        if 打印标题:
            print(f"    在库里叫这个标题：{'；'.join(打印标题)}")
        if 名次 == 1:
            print("    排第 1 名  [OK]")
        elif 名次 is None:
            print("    未上榜  [X]  （整个文件一个段落都没过阈值）")
        else:
            print(f"    排第 {名次} 名  [X]")

        for 名次2, (标题, 分, _原因) in enumerate(结果[:3], start=1):
            标记 = "  <- 标准答案" if 标题 in 这条的答案 else ""
            print(f"      {名次2}. {标题:<28} {分:.3f}{标记}")

        if 名次 is None:
            print("    间距：算不了（答案没上榜）")
        else:
            答分 = next(s for t, s, _ in 结果 if t in 这条的答案)
            错分 = max((s for t, s, _ in 结果 if t not in 这条的答案), default=None)
            if 错分 is None:
                print(f"    间距：{答分:.3f}（没有非答案上榜，无从比较）")
            else:
                print(f"    间距（答案 - 最高的非答案）：{答分 - 错分:+.3f}")
        print()

    # ---- ② 段落级：没被「前 3 段平均」磨掉间距之前长什么样 ----
    print("=" * 72)
    print("二、段落级间距（文件分是前 3 段平均来的，这个平均会把间距改写）")
    print("=" * 72)
    print("正确答案的段 vs 不相关的段，看最好的那两段差多少。\n")

    查询向量 = model.encode([用例["q"] for 用例 in QUERIES])
    段落分数 = cosine_similarity(查询向量, 段落向量)     # (查询数, 段数)

    for i, 用例 in enumerate(QUERIES, start=1):
        是答案 = np.array([t in 答案标题[用例["q"]] for t in 标题表])
        分数 = 段落分数[i - 1]
        答最高 = 分数[是答案].max() if 是答案.any() else float("nan")
        错最高 = 分数[~是答案].max() if (~是答案).any() else float("nan")
        过线 = int((分数 >= 当前默认阈值).sum())
        答过线 = int((分数[是答案] >= 当前默认阈值).sum()) if 是答案.any() else 0
        print(f"[{i}] 答案最好的一段 {答最高:.3f} / 不相关最好的一段 {错最高:.3f} "
              f"→ 间距 {答最高 - 错最高:+.3f}")
        print(f"    过 {当前默认阈值} 这条线：答案的段 {答过线}/{是答案.sum()}，"
              f"不相关的段 {过线 - 答过线}/{(~是答案).sum()}")

    # ---- ③ 阈值扫描：min_score 到底在不在干活 ----
    print("\n" + "=" * 72)
    print("三、阈值扫描：min_score 到底在不在干活")
    print("=" * 72)
    print("「放行率」= 全部查询 × 全部段落里，相似度过线的比例（所有查询合在一起算）。")
    print("放行率越接近 100%，说明这个阈值越没有在过滤。\n")
    print(f"  {'阈值':<8}{'放行段落':<14}{'放行率':<10}{'答案还能排第 1 的查询'}")
    print("  " + "-" * 56)
    for t in THRESHOLDS:
        放行 = int((段落分数 >= t).sum())
        总数 = 段落分数.size
        # 不只数「几条没过」，把没过的名字也记下来——光看 20/21 你不知道该查哪条。
        没过的 = []
        for 用例 in QUERIES:
            名次 = _排第几(search.search_semantic(用例["q"], top_k=999, min_score=t),
                          答案标题[用例["q"]])
            if 名次 != 1:
                没过的.append((用例["q"], 名次))
        标记 = "  <- 当前默认" if abs(t - 当前默认阈值) < 1e-9 else ""
        print(f"  {t:<8.2f}{放行}/{总数:<10}{放行 / 总数:>6.1%}    "
              f"{len(QUERIES) - len(没过的)}/{len(QUERIES)}{标记}")
        for q, 名次 in 没过的:
            说明 = "全被阈值砍了" if 名次 is None else f"第 {名次} 名"
            print(f"          └─ {q}（{说明}）")

    # ---- ④ 汇总 ----
    print("\n" + "=" * 72)
    print("四、汇总")
    print("=" * 72)
    print(f"  标准答案排第 1 的查询：{sum(1 for m in 排名汇总 if m == 1)}/{len(QUERIES)}")
    print(f"  上榜（排得上名次）的查询：{sum(1 for m in 排名汇总 if m is not None)}/{len(QUERIES)}")
    没排第一 = [用例["q"] for 用例, m in zip(QUERIES, 排名汇总) if m != 1]
    if 没排第一:
        print("  没排第 1 的查询（要看的话打开文件确认标准答案标得对不对）：")
        for q in 没排第一:
            print(f"    - {q}")
    else:
        print("  全部排第 1。")

    # ---- 安全网：确认没碰真库 ----
    真库 = _仓库根 / "studyorganizer.db"
    现在指纹 = 真库.stat().st_mtime_ns if 真库.exists() else None
    if args.真库指纹 != 现在指纹:
        print("\n!! 警告：仓库里的 studyorganizer.db 被动过了，这个脚本不该碰它。")
        return 1
    print("\n（仓库里的 studyorganizer.db 未被改动，本次跑的是临时库。）")

    # ---- 回归断言：--check 才有 ----
    # 放在安全网后面：不管检不检查，先确认没碰真库。
    if not args.check:
        return 0

    print("\n" + "=" * 72)
    print("回归检查")
    print("=" * 72)
    挂了 = [(用例, 名次) for 用例, 名次 in zip(QUERIES, 排名汇总) if 名次 != 1]
    if not 挂了:
        print(f"  PASS：{len(QUERIES)} 条查询的标准答案全部排在第 1。")
        return 0

    print(f"  FAIL：{len(挂了)}/{len(QUERIES)} 条查询的标准答案没排在第 1。")
    for 用例, 名次 in 挂了:
        说明 = "未上榜（一个段落都没过 min_score）" if 名次 is None else f"排第 {名次} 名"
        print(f"    [X] {用例['q']}  →  {说明}")
    print("\n  先别急着改检索代码。上面每条都可能是下面两种情况之一：")
    print("    a) 检索真的退化了；")
    print("    b) 这条查询的标准答案标错了（NOTES.md 第 8 条踩过）。")
    print("  打开上面列的文件读一遍再判断——标错的概率并不低。")
    return 1


def main():
    读参数 = argparse.ArgumentParser(description="StudyOrganizer 检索实测")
    读参数.add_argument("--model", default=None,
                     help="要测的向量模型名，默认用 search.MODEL_NAME")
    读参数.add_argument("--corpus", default="practice",
                     help="语料目录（相对仓库根目录），默认 practice")
    读参数.add_argument("--check", action="store_true",
                     help="回归检查：任何一条查询的标准答案没排第 1 就非 0 退出")
    args = 读参数.parse_args()

    if args.model is None:
        args.model = search.MODEL_NAME

    # 真库指纹：进临时目录之前先记下来，跑完对一下
    真库 = _仓库根 / "studyorganizer.db"
    args.真库指纹 = 真库.stat().st_mtime_ns if 真库.exists() else None

    return 跑一次(args)


if __name__ == "__main__":
    sys.exit(main())
