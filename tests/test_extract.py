from studyorganizer.extract import extract_title, extract_text


def test_标题去掉最终版():
    assert extract_title("practice/动态规划_最终版.pdf") == "动态规划"


def test_标题去掉副本():
    assert extract_title("practice/背包问题 - 副本.docx") == "背包问题"


def test_标题去掉定稿():
    assert extract_title("practice/期末试卷_定稿.pdf") == "期末试卷"


def test_读txt正文():
    # practice/讲义1.txt 的正文里应该包含"动态规划"
    text = extract_text("practice/讲义1.txt")
    assert "动态规划" in text
