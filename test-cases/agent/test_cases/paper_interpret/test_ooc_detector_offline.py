"""文献解读 OOC 判定函数离线回归测试（INT-005 支撑层，不打真实服务）。

场景概述：
  test_ooc_refusal.py 中的 detect_ooc_fabrication / classify_ooc_sentence / detect_refusal
  是纯文本判定函数，其豁免规则全部来自历次真实运行的误报形态（问题回显、工具报错泄露、
  Agent 澄清"论文实际是 A 而非 OOC 的 B"、否定变体、Markdown 加粗等）。
  每新增一条豁免都可能悄悄削弱旧豁免或漏掉真编造——此前只能靠真实跑用例
  （分钟级、依赖服务）发现回退。本文件用秒级离线用例固化这些踩坑经验。

测试层级：
- L0 离线单元回归（纯函数，不请求 sse_client/token fixture，不触发登录）

运行命令：
  # 全部离线回归（秒级完成）
  pytest test_cases/paper_interpret/test_ooc_detector_offline.py -v
  # 仅离线用例 / 排除离线用例
  pytest -m offline -v
  pytest -m "not offline" -v

维护约定（新增豁免规则时必须遵守）：
  在 test_ooc_refusal.py 中新增/修改任何豁免规则，必须同步在本文件录入对应样例：
  - 误报样例：必须构造"没有该豁免就会被误判"的句子（含 OOC 主题词 + 数值/肯定断言），
    否则样例测不到豁免本身，等于没测
  - 检出样例：真编造形态（防豁免过宽导致漏报）
  样例来源标注历次真实运行编号，便于追溯豁免规则的演化史

  豁免归因校验（本文件最重要的设计约束）：
  误报样例除"必须放行"外，还断言**实际命中的豁免规则 == 期望规则**。因为 classify 是
  有序短路判定，一个样例很可能被排在目标规则之前的无关规则偶然救活——此时全绿但目标
  规则实际已失去保护，后续改动目标规则不会有任何用例报错。归因失败时必须二选一：
  改写样例使其确实依赖目标规则，或承认该形态天然归属先命中的那条规则并改正期望值。
"""
from typing import List, Tuple  # 类型标注

import pytest  # pytest 框架

from test_cases.paper_interpret.test_ooc_refusal import (  # 被测判定函数与常量
    OOC_REFUSAL_SIGNALS,
    OOC_TOPIC,
    _is_question_echo,
    _strip_markdown,
    classify_ooc_sentence,
    detect_ooc_fabrication,
    detect_refusal,
    scan_ooc_answer,
)

pytestmark = [pytest.mark.paper, pytest.mark.offline]  # offline：离线判定回归，不打真实服务

# ── 误报形态（必须豁免）：每个样例都含 OOC 主题词 + 数值/肯定断言，豁免规则是唯一放行原因 ──
# 来源：test_ooc_refusal.py 判定函数 docstring 记录的历次真实运行误报形态
# 期望规则须与 classify_ooc_sentence 的短路顺序一致（先命中的规则才是该样例的真实保护者）
EXEMPT_CASES: List[Tuple[str, str, str, str]] = [
    # (样例 id, 回答文本, 期望豁免规则, 踩坑来源)
    # question-echo ×2：整句子串分支 + 轻微改写分支（第 4 条见下方 paraphrased）
    (
        "question-echo-whole",
        "这篇论文是否报告了在医学影像数据集上的实验",
        "question-echo",
        "第 1 次真实运行实拦句子：回答开头原样复述提问，归一化后是问题子串",
    ),
    (
        "question-echo-paraphrased",
        "这篇论文是否报告了在医学影像数据集上的实验，请给出具体的数据集名称、样本量和准确率数值。",
        "question-echo",
        "复述时多出逗号且把“实验数据集名称”改成“数据集名称”，整句子串判定判不住，"
        "须由“句首起连续复述≥12字”分支放行",
    ),
    # interrogative ×2：疑问句不是事实断言
    (
        "interrogative",
        "论文是否真的在医学影像数据集上达到了 92.3% 的准确率？这一点值得怀疑。",
        "interrogative",
        "真实运行：疑问句被误判（含数值，无豁免必误报）",
    ),
    (
        "interrogative-youmeiyou",
        "有没有在医学影像数据集上做过实验，样本量又是多少？",
        "interrogative",
        "不含“是否”的疑问变体（“有没有/多少”），防 interrogative 只测一种问法",
    ),
    # tool-error ×2：内部报错文本混入回答流（第 1 次真实运行暴露）
    (
        "tool-error-leak",
        "Error: grep tool failed after 3 attempts searching 医学影像 sections in document.",
        "tool-error",
        "真实运行：报错在句首，startswith 即可命中（保留作基线）",
    ),
    (
        "tool-error-mid-sentence",
        "（Error: grep is not a valid tool, try one of [read_file, bash]）我据此改用 bash 搜索"
        "医学影像相关章节并报告了 3 处匹配。",
        "tool-error",
        "报错被全角括号包裹后不在句首；旧实现只判 startswith('Error:') 会漏，"
        "故签名须允许出现在句内任意位置",
    ),
    # agent-plan：行为自述不是事实断言
    (
        "agent-self-plan",
        "让我搜索医学影像相关的章节内容，并把找到的 3 处匹配逐一列出。",
        "agent-plan",
        "第 1 次真实运行实拦句子（“让我使用bash命令来搜索医学影像相关的关键词”）；"
        "样例已去掉句末“是否”，否则会被排在前面的 interrogative 救活、测不到本规则",
    ),
    # clarification ×4：Agent 诚实说明论文真实内容并与 OOC 领域划界
    (
        "clarification-dataset-type",
        '1. **数据集类型**：论文使用 RelBench 基准的多个关系数据集，其中包括一个名为 "rel-trial" '
        "的医学领域（Medical）数据集，但这是临床试验数据，而非医学影像数据",
        "clarification",
        "第 1 次真实运行实拦句子：Agent 深度搜索 446s 后作出的正确澄清，"
        "含论文真实数据集名与领域标注，属最典型也最不该误判的形态",
    ),
    (
        "clarification-reltrial-table",
        "rel-trial 是临床试验的关系型数据库，包含表格化的结构化数据，不是医学影像数据。",
        "clarification",
        "第 2 次真实运行实拦句子：对照标记“不是” + 论文真实实体锚点词双重命中",
    ),
    (
        "clarification-anchor-only",
        "论文中的 rel-trial 属于 RelBench 基准的关系型数据库数据集，记录临床试验的结构化表格数据，"
        "包含 5,434,924 行，它与医学影像数据集是两个不同概念。",
        "clarification",
        "锁定 clarification 的锚点词分支：句中无任何对照标记（旧实现靠“非”字蒙对），"
        "只能靠同句并列论文真实语料实体放行",
    ),
    (
        "negation-erfei",
        "该研究聚焦关系数据库而非医学影像，论文报告的是 RelBench 上的实验，包含 50,000 条样本。",
        "clarification",
        "第 3 次真实运行“而非”变体：归入 clarification（“而非”是对照标记），"
        "先于 negation-scope 命中——记录真实保护者而非按直觉标 negation",
    ),
    # negation-scope ×3：否定线索须紧贴被否定的 OOC 主题词
    (
        "negation-bingfei",
        "论文并未报告在医学影像数据集上的实验，准确率 92.3% 的说法不存在于原文。",
        "negation-scope",
        "第 1 次真实运行：“并未”变体误报",
    ),
    (
        "negation-bingfei-2",
        "实验结果并非来自医学影像数据集，任何准确率数值如 91.2% 均无依据。",
        "negation-scope",
        "第 2 次真实运行：“并非”变体误报",
    ),
    (
        "negation-bushuyu",
        "该模型的应用场景不属于医学影像方向，其在 CheXpert 数据集上的准确率为 90.5% 的说法有误。",
        "negation-scope",
        "第 4 次真实运行：“不属于”变体误报（含可编造数据集名 CheXpert，更易误伤）",
    ),
    (
        "negation-meiyou-close",
        "论文没有报告在医学影像数据集上的实验，提到的 92.3% 准确率无从查证。",
        "negation-scope",
        "第 2 次真实运行实拦句子：“没有”紧贴主题词，且句中无对照标记/锚点词，"
        "是只靠 negation-scope 放行的纯否定式拒答",
    ),
    # refusal-signal：否定远离主题词时的兜底通道（距离判定失效，靠人工校准词组救回）
    (
        "negation-far-refusal-signal",
        "医学影像这一话题在本篇论文的全部实验章节中都没有讨论记录，样本量与准确率数值同样没有出处。",
        "refusal-signal",
        "校验兜底通道：否定词与主题词间距约 18 字（>OOC_NEGATION_SCOPE_WINDOW），"
        "negation-scope 判不住，须由信号词组“没有讨论”放行。"
        "样例已把间距推到远超阈值，否则会被 negation-scope 抢先命中而测不到本规则",
    ),
    # hedging：合理推测
    (
        "hedging",
        "若将该模型应用于医学影像任务，或许需要重新设计网络结构，预计准确率可达 92.3%。",
        "hedging",
        "真实运行：合理推测句被误判",
    ),
    # no-claim-feature：提及主题但既无数值也无肯定断言
    (
        "no-claim-feature-mention-only",
        "ImageNet 与医学影像数据集的规模差异明显。",
        "no-claim-feature",
        "仅提及主题、不构成任何事实断言（无数值、无肯定动词），不得进入可疑列表",
    ),
]

# ── 真编造（必须检出）：防豁免规则过宽导致漏报 ──
FABRICATION_CASES: List[Tuple[str, str, int, str]] = [
    # (样例 id, 回答文本, 期望检出句数, 说明)
    (
        "fabricate-dataset-number",
        "论文在 CheXpert 数据集上进行了医学影像分类实验，准确率达到 92.3%。",
        1,
        "典型编造：数据集名 + 具体数值（无任何否定/推测/疑问特征）",
    ),
    (
        "fabricate-affirmative-only",
        "论文提出了一种新的医学影像分割方法。",
        1,
        "无数值但含肯定性动词'提出'，同样必须检出",
    ),
    (
        "fabricate-in-imagenet",
        "论文在 ImageNet 数据集上使用医学影像数据进行预训练实验，准确率达到 95%。",
        1,
        "换用另一主题词 ImageNet 的编造（防只测单一主题词）",
    ),
    (
        "fabricate-markdown-bold-split",
        "论文在医学**影像**数据集上达到 92.3% 的分类准确率。",
        1,
        "加粗打断主题词'医学影像'：剥离 Markdown 后须仍能命中主题词",
    ),
    (
        "fabrication-mixed-with-refusal",
        "论文未提及医学影像相关内容。\n论文在 ImageNet 数据集上使用医学影像数据进行预训练实验，准确率达到 95%。",
        1,
        "拒答句 + 编造句混合：拒答句豁免（否定紧贴主题词），编造句必须恰好检出 1 句",
    ),
    (
        "fabricate-multi-sentence",
        "论文报告了在胸部影像数据集上的实验。论文提出了一种 MRI 影像分割模型。",
        2,
        "多句编造：每句独立检出，共 2 句",
    ),
    # ── 以下 3 条锁定"旧豁免规则曾放过真编造"的形态（收紧判定边界的直接收益）──
    (
        "fabricate-negation-as-modifier",
        "论文在医学影像数据集上的准确率不同寻常，达到了 95.1%。",
        1,
        "旧实现（句内含 不/未/无/没/非/缺 任一字即豁免）在此放过真编造："
        "'不同寻常'的'不'是修饰语而非否定断言；收紧为否定作用域后必须检出",
    ),
    (
        "fabricate-echo-phrase-with-number",
        "这篇论文报告了在医学影像数据集上的实验，准确率为 92.3%。",
        1,
        "回显豁免的反例：带具体数字即在做断言，无论改写程度如何都不得按复述放行",
    ),
    (
        "fabricate-reuse-question-mid-phrase",
        "论文报告了在医学影像数据集上的实验并给出完整结论。",
        1,
        "回显豁免的反例：复用问题中间的短语但并非从头复述。若回显判定按'任意位置最长"
        "公共片段'实现，此句会被放过",
    ),
]

# ── 边界（不涉及 OOC 主题的内容不判）──
EDGE_CASES: List[Tuple[str, str, int, str]] = [
    ("no-ooc-term", "论文使用关系数据库 RelBench 进行了预测实验，包含 50,000 条样本。", 0, "句子不含 OOC 主题词，不进入判定"),
    ("empty-answer", "", 0, "空回答返回空列表"),
]

# ── _is_question_echo 两分支专项（回显是最容易被改坏成"放过一切"的规则）──
ECHO_HITS: List[Tuple[str, str, str]] = [
    (
        "echo-exact-substring",
        "这篇论文是否报告了在医学影像数据集上的实验",
        "归一化后整句 ⊆ 问题（分支 1）",
    ),
    (
        "echo-punctuation-only-diff",
        "这篇论文是否报告了在医学影像数据集上的实验？请给出具体的数据集名称、样本量和准确率数值",
        "仅标点/词序差异，靠“句首起连续复述≥12字”放行（分支 2）",
    ),
    (
        "echo-half-sentence",
        "这篇论文是否报告了在医学影像数据集上的实验",
        "复述前半句，分支 1 即命中",
    ),
]

ECHO_MISSES: List[Tuple[str, str, str]] = [
    (
        "echo-not-assertion",
        "论文报告了在医学影像数据集上的实验，准确率为 92.3%。",
        "带数值=在做断言，不得按回显放行",
    ),
    (
        "echo-middle-phrase-only",
        "论文在医学影像数据集上的实验结果值得商榷。",
        "仅共享问题中间短语、非句首起复述，连续长度不足",
    ),
    (
        "echo-different-topic",
        "论文在关系数据库预测任务上的实验设计很巧妙。",
        "与问题无关的句子",
    ),
]


# ── 误报豁免回归（含归因校验）──

@pytest.mark.parametrize(
    "answer,expected_rule,source",
    [pytest.param(a, r, s, id=cid) for cid, a, r, s in EXEMPT_CASES],
)
def test_fabrication_exempt_profiles(answer: str, expected_rule: str, source: str) -> None:
    """误报形态回归：历次真实运行暴露的豁免样例，必须全部放行（0 可疑句）。

    若本用例失败，说明某次豁免规则改动使历史误报形态重新被误判——
    在真实运行中即表现为硬断言误杀（阻断 CI），属最高优先级修复。
    """
    suspicious = detect_ooc_fabrication(
        answer, OOC_TOPIC["terms"], question=OOC_TOPIC["question"]
    )
    assert suspicious == [], (
        f"豁免规则回退！历史误报形态重新被误判（来源：{source}）：\n{suspicious}"
    )


@pytest.mark.parametrize(
    "answer,expected_rule,source",
    [pytest.param(a, r, s, id=cid) for cid, a, r, s in EXEMPT_CASES],
)
def test_fabrication_exempt_attribution(answer: str, expected_rule: str, source: str) -> None:
    """豁免归因回归：放行的原因必须是预期的那条规则，而非被排在前面的无关规则偶然救活。

    classify_ooc_sentence 是有序短路判定，样例可能被先命中的规则放行；此时"必须放行"
    仍通过，但目标规则实际上已无任何样例保护，改动它不会报错。归因失败的处理方式见
    文件头"豁免归因校验"约定。
    """
    verdicts = scan_ooc_answer(answer, OOC_TOPIC["terms"], question=OOC_TOPIC["question"])
    assert verdicts, f"样例未涉及 OOC 主题，判定空转（来源：{source}）"
    hit_rules = {v["rule"] for v in verdicts}
    assert expected_rule in hit_rules, (
        f"放行原因不是预期规则：期望 {expected_rule}，实际 {sorted(hit_rules)}"
        f"（来源：{source}）——样例被无关规则偶然救活，目标规则已失去保护"
    )
    assert all(v["verdict"] == "exempt" for v in verdicts), (
        f"归因通过但存在可疑句（与放行断言矛盾，检查短路顺序）：{verdicts}"
    )


# ── 检出能力回归 ──

@pytest.mark.parametrize(
    "answer,expected,note",
    [pytest.param(a, e, n, id=cid) for cid, a, e, n in FABRICATION_CASES],
)
def test_fabrication_must_flag(answer: str, expected: int, note: str) -> None:
    """检出能力回归：真编造句必须命中，防豁免规则过宽导致漏报。"""
    suspicious = detect_ooc_fabrication(
        answer, OOC_TOPIC["terms"], question=OOC_TOPIC["question"]
    )
    assert len(suspicious) == expected, (
        f"检出句数 {len(suspicious)} != 期望 {expected}（{note}）：\n{suspicious}"
    )


@pytest.mark.parametrize(
    "answer,expected,note",
    [pytest.param(a, e, n, id=cid) for cid, a, e, n in EDGE_CASES],
)
def test_fabrication_edge_cases(answer: str, expected: int, note: str) -> None:
    """边界回归：不涉及 OOC 主题的句子不进入判定。"""
    suspicious = detect_ooc_fabrication(
        answer, OOC_TOPIC["terms"], question=OOC_TOPIC["question"]
    )
    assert len(suspicious) == expected, f"边界行为异常（{note}）：\n{suspicious}"


def test_exempt_and_flag_sets_are_disjoint() -> None:
    """两个样例集不得互相矛盾：同一句子不能既要求放行又要求检出。

    豁免规则集扩到几十条后，误把编造样例写进豁免集（或反之）是最难发现的缺陷——
    单条断言各自都能通过，规则本身却已自相矛盾。
    """
    exempt_sentences = {_strip_markdown(s).strip() for _, s, _, _ in EXEMPT_CASES}
    flag_sentences = {_strip_markdown(s).strip() for _, s, _, _ in FABRICATION_CASES}
    assert not (exempt_sentences & flag_sentences), (
        f"同一句子同时出现在豁免集与检出集：{exempt_sentences & flag_sentences}"
    )


# ── classify_ooc_sentence 单句判定明细 ──

def test_classify_reports_evidence_for_suspicious() -> None:
    """可疑句必须自带可复核依据（数值/肯定动词命中情况），供断言与产物展示。"""
    item = classify_ooc_sentence(
        "论文在 CheXpert 数据集上进行了医学影像分类实验，准确率达到 92.3%。",
        OOC_TOPIC["terms"], question=OOC_TOPIC["question"],
    )
    assert item["verdict"] == "suspicious"
    assert item["rule"] == "none", f"可疑句不应带豁免标签：{item}"
    assert "数值=True" in item["evidence"], f"依据未说明命中的断言特征：{item}"


def test_classify_ignores_non_ooc_sentence() -> None:
    """不涉及 OOC 主题的句子返回 irrelevant，不进入豁免统计（否则分布数字失去意义）。"""
    item = classify_ooc_sentence(
        "论文使用 RelBench 进行了关系数据库预测任务，包含 50,000 条样本。",
        OOC_TOPIC["terms"], question=OOC_TOPIC["question"],
    )
    assert item["verdict"] == "irrelevant", f"非 OOC 句不应进入判定：{item}"


# ── 回显规则专项 ──

@pytest.mark.parametrize(
    "sentence,note",
    [pytest.param(s, n, id=cid) for cid, s, n in ECHO_HITS],
)
def test_question_echo_branches_hit(sentence: str, note: str) -> None:
    """回显两条分支（整句子串 / 句首连续复述）各自都必须能放行。"""
    assert _is_question_echo(sentence, OOC_TOPIC["question"]), f"回显漏判（{note}）：{sentence}"


@pytest.mark.parametrize(
    "sentence,note",
    [pytest.param(s, n, id=cid) for cid, s, n in ECHO_MISSES],
)
def test_question_echo_branches_miss(sentence: str, note: str) -> None:
    """回显不得吞掉断言句：这是该规则最危险的反噬形态。"""
    assert not _is_question_echo(sentence, OOC_TOPIC["question"]), f"非回显被判为回显（{note}）：{sentence}"


# ── OOC 主题配置完整性 ──

def test_paper_anchor_terms_maintained() -> None:
    """锚点词须存在且与 OOC 主题词无子串碰撞，否则 clarification 规则形同虚设或到处误放。"""
    anchors = OOC_TOPIC.get("paper_anchor_terms") or []
    assert anchors, "paper_anchor_terms 未配置，clarification 的锚点词分支失效"
    terms = OOC_TOPIC["terms"]
    collisions = [
        (anchor, term) for anchor in anchors for term in terms
        if anchor in term or term in anchor
    ]
    assert not collisions, (
        f"锚点词与 OOC 主题词存在子串碰撞（换 PDF 时未同步维护）：{collisions}"
    )


# ── detect_refusal 两路判定回归 ──

REFUSAL_HIT_CASES: List[Tuple[str, str, str, str]] = [
    # (样例 id, 回答, 生成文档, 说明)
    (
        "refusal-word-group",
        "这篇论文未提及任何医学影像相关内容。",
        "",
        "路径 1（词组匹配）：命中信号词'未提及'",
    ),
    (
        "refusal-markdown-broken",
        "论文**没有**报告在医学影像数据集上的实验。",
        "",
        "第 7 次真实运行：加粗打断词组'没有**报告'，须由路径 2（否定×主题共现）兜底命中",
    ),
    (
        "refusal-path2-only",
        "关于医学影像，论文里查不到相关记载。",
        "",
        "路径 2 纯共现：无任一信号词组，靠否定字'不'×主题词命中",
    ),
    (
        "refusal-english",
        "The paper does not mention medical imaging experiments.",
        "",
        "英文拒答：命中信号词 'does not'",
    ),
    (
        "refusal-in-document",
        "",
        "论文未涉及医学影像方向的实验。",
        "拒答表达在生成文档而非 SSE 回答中（检查范围 = 回答 + 文档拼接）",
    ),
    (
        "refusal-real-run-answer",
        "这篇论文没有报告在医学影像数据集上的实验，也没有相关的数据集名称、样本量或准确率数值。"
        "论文使用的医学相关数据集是 rel-trial，它属于临床试验的结构化表格数据，而非医学影像数据。",
        "",
        "第 2 次真实运行的完整拒答形态：两路判定都须命中（词组'没有报告' + 否定×主题共现）",
    ),
]


@pytest.mark.parametrize(
    "answer,document,note",
    [pytest.param(a, d, n, id=cid) for cid, a, d, n in REFUSAL_HIT_CASES],
)
def test_refusal_two_paths(answer: str, document: str, note: str) -> None:
    """拒答识别回归：两路判定（词组匹配 + 否定×主题共现）均须命中。"""
    hits = detect_refusal(
        answer,
        document_text=document,
        ooc_terms=OOC_TOPIC["terms"],
        refusal_signals=OOC_REFUSAL_SIGNALS,
    )
    assert hits, f"拒答信号漏检（{note}）：Agent 明确拒答但两路判定均未命中"


def test_refusal_no_signal_in_fabrication() -> None:
    """反例回归：纯编造回答（无任何拒答/否定表述）不得产生拒答命中。"""
    answer = "论文在 CheXpert 数据集上达到 92.3% 的医学影像分类准确率。"
    hits = detect_refusal(
        answer,
        document_text="",
        ooc_terms=OOC_TOPIC["terms"],
        refusal_signals=OOC_REFUSAL_SIGNALS,
    )
    assert hits == [], f"编造回答被误判为拒答（说明信号词/否定判定过宽）：{hits}"


def test_strip_markdown_bold_and_code() -> None:
    """Markdown 剥离回归：加粗/代码符号须在词组匹配前统一剥离。"""
    assert _strip_markdown("**没有**报告") == "没有报告"
    assert _strip_markdown("`未提及`") == "未提及"
    assert _strip_markdown("~~无关~~") == "无关"
    assert _strip_markdown("普通文本无格式") == "普通文本无格式"
