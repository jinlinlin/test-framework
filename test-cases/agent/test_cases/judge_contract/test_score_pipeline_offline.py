"""评分收口链离线契约：Judge 打分 → score_sink → junit <properties> 的可执行断言。

为什么要有这个文件（引擎侧 _to_result 的 properties 契约在源仓不存在，
两侧必须有一把锁钉住量纲与字段名，否则引擎静默按"非评分类"收口）：
    1) score 必须是 0~1 归一比（5 分制 ÷ scale）——若哪天有人改成直写
       5 分制，引擎 default_threshold=0.75 会把所有用例判成超标，无声失效；
    2) average 必须代码重算——裁判 LLM 自报 average 常算错（源仓已知行为），
       judge_client 重算 + score_sink 再重算，双保险都要钉住；
    3) dimensions 键名必须保持 core.constants 的英文维度名——跨引擎趋势
       按该词表聚合，改名即断链。

运行（秒级、本地假裁判、不烧 Judge token）：
    python -m pytest test_cases/judge_contract -q
"""
import pytest

from core.clients.judge_client import JudgeClient
from core.constants import SUBJECTIVE_DIMENSIONS
from core.testing.fake_judge import DEFAULT_SCORES, FakeJudge

pytestmark = [pytest.mark.judge, pytest.mark.offline]

# 引擎 defaults 的 default_threshold 同标度契约值（0~1 比率制）
PASS_RATIO = 0.75


@pytest.fixture(scope="module")
def judge_server():
    """模块级假裁判：起一次本地端口，全文件复用。"""
    with FakeJudge() as j:
        yield j


@pytest.fixture
def client(judge_server: FakeJudge) -> JudgeClient:
    """指向假裁判的评审客户端（显式传参，不依赖 config/.env 的 JUDGE_*）。"""
    return JudgeClient(base_url=judge_server.base_url, api_key="mock-key", model="mock-judge")


@pytest.fixture(autouse=True)
def _reset_judge(judge_server: FakeJudge):
    """每条用例前复位预设评分：module 级假服务若跨用例残留状态，
    低分用例会把下一条的评分钉在 2.0（首轮实跑已暴露该坑）。"""
    judge_server.set_scores(dict(DEFAULT_SCORES))
    judge_server.extra_fields = {}


class TestScorePipeline:
    """收口主链：高分归一、量纲、properties 字段名。"""

    def test_高分归一为比率并写入properties(self, client: JudgeClient, judge_server: FakeJudge, score_sink, request):
        result = client.evaluate(question="什么是RAG？", answer="检索增强生成……")
        score = score_sink(result)
        # 六维默认 4.5/5 → 0.9，量纲契约：0~1 比率制
        assert score == 0.9
        assert score >= PASS_RATIO
        props = dict(request.node.user_properties)
        assert props["score"] == "0.9"
        assert "threshold" not in props, "用例未显式声明阈值时不得写入，留给引擎默认阈值回退"
        # prompt 契约：评分标准全文与结构化输出要求必须随请求抵达裁判侧
        body = judge_server.requests[-1]
        assert "评分标准" in body["messages"][1]["content"]
        assert body["response_format"] == {"type": "json_object"}

    def test_llm自报average被代码重算覆盖(self, client: JudgeClient, judge_server: FakeJudge, score_sink):
        """裁判顶层写入错误 average（1.0），score_sink 仍须按维度重算得 0.9。"""
        judge_server.set_average(1.0)
        result = client.evaluate(question="什么是RAG？", answer="检索增强生成……")
        # judge_client 内部已重算覆盖：result["average"] 应为维度均值 4.5 而非 1.0
        assert result["average"] == 4.5
        assert score_sink(result) == 0.9

    def test_低分场景收口正确且判定归用例侧(self, client: JudgeClient, judge_server: FakeJudge, score_sink, request):
        """双轨契约：status 由 pytest 断言决定，score 仅作报告元数据。

        真实评分类用例会在此处 assert score >= threshold 而自然 fail；本用例断言
        的是收口层行为——低分必须被如实收口为低比率，而不是被钳位或丢弃。
        """
        judge_server.set_scores({d: 2.0 for d in SUBJECTIVE_DIMENSIONS})  # 旧格式数字直填
        result = client.evaluate(question="什么是RAG？", answer="答非所问")
        score = score_sink(result)
        assert score == 0.4
        assert not (score >= PASS_RATIO), "低分不得被误判为达标"
        props = dict(request.node.user_properties)
        dimensions = props["dimensions"]
        for dim in SUBJECTIVE_DIMENSIONS:
            assert f'"{dim}"' in dimensions, "dimensions 键名必须保持英文维度词表"

    def test_显式threshold随properties落盘(self, client: JudgeClient, score_sink, request):
        score = score_sink(client.evaluate(question="q", answer="a"), threshold=0.8)
        props = dict(request.node.user_properties)
        assert score == 0.9
        assert props["threshold"] == "0.8"
