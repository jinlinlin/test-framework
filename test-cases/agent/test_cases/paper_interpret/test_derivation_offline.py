"""派生逻辑离线回归（迁移精选版）：配置读取、环境切换、温度契约、Judge 纯函数的零依赖断言。

借鉴被测项目 llm-api 的 `testConfig_DefaultUrl` 思路——不搭 mock、不发请求，
只对"输入决定输出"的函数直接给期望值。选这些函数打测试的理由是它们都真实坑过：

1) require 的中文报错：新人没配 .env 时，报错信息能否直接指向修复动作，决定他要问多久。
2) 布尔开关：CLEANUP_AFTER_TEST / JUDGE_GATE / USE_DEEPEVAL 都只认字面 "true"。
   有人配 1/yes 就静默关闭门禁，且看不出被关。
3) JUDGE_TEMPERATURE：kimi-k3 等推理模型不支持 temperature 参数（硬编码 0.1 曾让裁判全军覆没
   于 HTTP 400），取值规则是"未配置默认 0.1 / 留空或 none 不传 / 数值透传"，且请求体组装须同步锁定。
4) _best_window_pos / _extract_claims：声明定位与文本清洗契约（源仓 2026-11-05 核查沉淀）。
5) build_optimized_scores：落盘 judge.json 的组装契约（忠实度理由曾恒为空串）。

维护约定：改动 core/utils/config.py 或 judge_client 取值规则时，先在这里加/改断言，再改实现。

迁移记录（相对源仓 test_derivation_offline.py 的 57 条）：
- 本文件收录 config/环境/温度/Judge 纯函数/scores 组装共 8 个测试类；
- 未收录 TestNormPdfPath、TestGoldenMatchingRules（依赖 golden_dataset 模块，本仓未迁移）、
  TestFaithfulnessReason、TestFaithfulnessUnlocatedDisclosure（依赖 langfuse_integration，
  在 Langfuse 钩子回补清单内）——回补对应模块时应同步回补这些用例；
- TestBooleanSwitchParsing 的 ACCESSORS 去掉 GOLDEN_STRICT 项（黄金集开关本仓未启用）。

运行：
    python -m pytest test_cases/paper_interpret/test_derivation_offline.py -q
    python -m pytest -m offline -q
"""
import pytest
import yaml

from core.clients import judge_client as judge_client_module
from core.clients.judge_client import JudgeClient
from core.constants import ALL_JUDGE_DIMENSIONS
from core.utils import config as config_module
from core.utils.config import (
    DEFAULT_AUTHORIZATION,
    PROJECT_ROOT,
    Config,
    ConfigError,
    _resolve_env_name,
)
from test_cases.paper_interpret.test_paper_common import build_optimized_scores  # 落盘 scores 组装纯函数

pytestmark = [pytest.mark.offline]


class TestConfigReadRules:
    """配置读取契约：缺失/空白的判定、必填报错的可诊断性。"""

    def test_get对空白与缺失一律返回None(self, monkeypatch):
        c = Config()
        monkeypatch.setenv("AGENT_TEST_KEY_MISSING", "")  # 空串
        assert c.get("AGENT_TEST_KEY_MISSING") is None
        monkeypatch.setenv("AGENT_TEST_KEY_MISSING", "   ")  # 纯空白
        assert c.get("AGENT_TEST_KEY_MISSING") is None
        monkeypatch.delenv("AGENT_TEST_KEY_MISSING", raising=False)
        assert c.get("AGENT_TEST_KEY_MISSING") is None
        monkeypatch.setenv("AGENT_TEST_KEY_MISSING", "  value  ")
        assert c.get("AGENT_TEST_KEY_MISSING") == "value", "get 应去首尾空白"

    def test_require缺失时报错指向修复动作(self, monkeypatch):
        c = Config()
        monkeypatch.delenv("AGENT_TEST_REQUIRED", raising=False)
        with pytest.raises(ConfigError) as exc:
            c.require("AGENT_TEST_REQUIRED", "测试用途键")
        msg = str(exc.value)
        assert "AGENT_TEST_REQUIRED" in msg and "config/.env.example" in msg, (
            f"报错必须同时给出键名与修复入口，实际：{msg}"
        )

    def test_token运行时注入优先于环境变量(self, monkeypatch):
        c = Config()
        monkeypatch.setenv("TOKEN", "token-from-env")
        assert c.token == "token-from-env"
        c.set_runtime_token("token-injected")  # 登录/续期后注入
        assert c.token == "token-injected"
        assert c.get("TOKEN") == "token-injected", "注入须同步环境变量，否则其它读取点仍拿旧值"

    def test_authorization未配置时回退内置客户端凭据(self, monkeypatch):
        c = Config()
        monkeypatch.delenv("AUTHORIZATION", raising=False)
        assert c.authorization == DEFAULT_AUTHORIZATION
        monkeypatch.setenv("AUTHORIZATION", "Basic custom")
        assert c.authorization == "Basic custom"


class TestBooleanSwitchParsing:
    """布尔开关共用同一套取值规则，逐个测以防有人只改一处。

    （源仓另有 GOLDEN_STRICT 项，依赖 golden_dataset 模块，本仓未启用故不收录。）
    """

    ACCESSORS = {
        "CLEANUP_AFTER_TEST": lambda c: c.cleanup_after_test,
        "JUDGE_GATE": lambda c: c.judge_gate,
        "USE_DEEPEVAL": lambda c: c.use_deepeval,
    }

    @pytest.mark.parametrize("key,accessor", list(ACCESSORS.items()))
    @pytest.mark.parametrize("value,expected", [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        (" true ", True),          # 允许带空白
        ("false", False),
        ("", False),               # 空值视为关闭
        ("1", False),              # 契约：只认字面 true，配 1 不生效（用例显式断言而非默认它可用）
        ("yes", False),
        (None, False),             # 未配置 → 默认关闭
    ])
    def test_开关取值规则(self, key, accessor, value, expected, monkeypatch):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
        assert accessor(Config()) is expected, f"{key}={value!r} 解析结果不符契约"


class TestJudgeTemperatureParsing:
    """JUDGE_TEMPERATURE 取值契约：未配置默认 0.1；留空/none/off 不传；非法值报中文错。

    与布尔开关刻意不同：本键直接读原始环境变量区分"未配置"与"显式留空"
    （get() 会把两者都归为 None，无法表达"留空=不传"）。
    """

    def test_未配置时默认低采样(self, monkeypatch):
        monkeypatch.delenv("JUDGE_TEMPERATURE", raising=False)
        assert Config().judge_temperature == 0.1

    @pytest.mark.parametrize("value", ["", "   ", "none", "NONE", "off"])
    def test_留空或none表示不传该参数(self, value, monkeypatch):
        monkeypatch.setenv("JUDGE_TEMPERATURE", value)
        assert Config().judge_temperature is None, f"{value!r} 应解析为不传"

    @pytest.mark.parametrize("value,expected", [("0.1", 0.1), ("0.7", 0.7), (" 0.3 ", 0.3)])
    def test_数值正常解析并去空白(self, value, expected, monkeypatch):
        monkeypatch.setenv("JUDGE_TEMPERATURE", value)
        assert Config().judge_temperature == expected

    def test_非法值报中文配置错(self, monkeypatch):
        monkeypatch.setenv("JUDGE_TEMPERATURE", "high")
        with pytest.raises(ConfigError, match="JUDGE_TEMPERATURE"):
            _ = Config().judge_temperature


class TestJudgeRequestBodyTemperature:
    """请求体温度锁：temperature 是否进入请求体由 JUDGE_TEMPERATURE 决定。

    锁的是源仓 2026-11-05 修复本体——kimi-k3 不支持 temperature=0.1（网关返回
    HTTP 400 InvalidParameter）。硬编码一旦被"顺手加回"，kimi-k3 裁判立刻全军覆没。
    假客户端只捕获请求体，不发真实请求（替换 httpx.Client，不打真服务）。
    """

    ENV = {
        "JUDGE_BASE_URL": "http://judge.local/v1",
        "JUDGE_API_KEY": "sk-test-offline",
        "JUDGE_MODEL": "kimi-k3",
    }

    def _call_and_capture(self, monkeypatch, temperature) -> dict:
        """构造 JudgeClient 并拦截 _call_llm 的请求体。temperature=None 表示未配置。"""
        for k, v in self.ENV.items():
            monkeypatch.setenv(k, v)
        if temperature is None:
            monkeypatch.delenv("JUDGE_TEMPERATURE", raising=False)
        else:
            monkeypatch.setenv("JUDGE_TEMPERATURE", temperature)
        client = JudgeClient()
        captured = {}

        class _Resp:
            status_code = 200

            def json(self):
                return {"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {}}

        class _FakeHttpClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def post(self, url, headers=None, json=None):
                captured["body"] = json
                return _Resp()

        monkeypatch.setattr(judge_client_module.httpx, "Client", _FakeHttpClient)
        client._call_llm("system", "user")
        return captured["body"]

    def test_配none时请求体不含temperature(self, monkeypatch):
        body = self._call_and_capture(monkeypatch, "none")
        assert "temperature" not in body, "kimi-k3 不支持 temperature，传了必 HTTP 400"

    def test_未配置时请求体带默认01(self, monkeypatch):
        body = self._call_and_capture(monkeypatch, None)
        assert body.get("temperature") == 0.1, "未配置须保持原默认行为（低采样）"

    def test_自定义数值透传进请求体(self, monkeypatch):
        body = self._call_and_capture(monkeypatch, "0.7")
        assert body.get("temperature") == 0.7


class TestBestWindowPos:
    """高频关键词多候选定位契约（源仓 2026-11-05 核查）：RelBench 在论文里出现 22 次，
    首命中在摘要（位置 707），±500 窗口内没有"7 domains/30 tasks"，声明被判 unknown；
    位置 2169 的窗口才含数据。取"数字密度最高窗口"后该声明才能被正确验证。"""

    def test_高频词选数字密度最高窗口(self):
        reference = ("引言提到 RelBench 基准。" + "填充" * 300
                     + "RelBench 再次出现。" + "填充" * 300
                     + "RelBench 包含 7 个数据库与 30 个任务。")
        pos = JudgeClient._best_window_pos(reference, "RelBench", "RelBench 含 7 个库 30 个任务", 50)
        assert pos == reference.rfind("RelBench"), "应选中含数字的窗口而非首命中"
        assert "7" in reference[pos - 50: pos + 60]

    def test_无数字token时回退首命中(self):
        reference = "A term here. " * 5 + "term again"
        assert JudgeClient._best_window_pos(reference, "term", "该术语描述了方法") == reference.find("term")

    def test_关键词不存在返回负一(self):
        assert JudgeClient._best_window_pos("some text", "absent", "声明含 5 个") == -1

    def test_候选扫描数量受max_hits限制(self):
        reference = ("kw 无数字段 " * 40) + "kw 含 42 数据"
        pos = JudgeClient._best_window_pos(reference, "kw", "共 42 项", 20, max_hits=5)
        assert pos == reference.find("kw"), "超出 max_hits 的候选不再扫描（回退首命中）"


class TestExtractClaimsCleanup:
    """声明文本清洗契约：LLM 切句常残留前导标点（实测一轮 10/10 声明带前导 "."），
    污染落盘展示与关键词提取。"""

    def _client(self, monkeypatch, claims):
        for k, v in TestJudgeRequestBodyTemperature.ENV.items():
            monkeypatch.setenv(k, v)
        client = JudgeClient()
        monkeypatch.setattr(client, "_call_llm", lambda **kw: {"claims": claims})
        return client

    def test_前导标点被清洗(self, monkeypatch):
        client = self._client(monkeypatch, [".RelBench 含 7 个库", "。中文声明", "- 列表项声明"])
        assert client._extract_claims("回答") == ["RelBench 含 7 个库", "中文声明", "列表项声明"]

    def test_空串与非字符串被过滤(self, monkeypatch):
        client = self._client(monkeypatch, ["  ", "", "有效声明", None, 3])
        assert client._extract_claims("回答") == ["有效声明"]

    def test_数组返回形态同样清洗(self, monkeypatch):
        for k, v in TestJudgeRequestBodyTemperature.ENV.items():
            monkeypatch.setenv(k, v)
        client = JudgeClient()
        monkeypatch.setattr(client, "_call_llm", lambda **kw: [".数组形态声明"])
        assert client._extract_claims("回答") == ["数组形态声明"]


class TestOptimizedScores:
    """落盘 judge.json 的 scores 组装契约（源仓 2026-11-05 核查：忠实度理由此前恒为空串，
    只修了 Langfuse 上报侧，落盘组装是另一条路）。"""

    def _judge_result(self):
        return {
            "relevance": 5, "completeness": 5, "depth": 5, "instruction_follow": 5,
            "format": 5, "key_concepts": 5, "faithfulness": 3.0,
            "supported_claims": 5, "total_claims": 10, "unlocated_claims": 1,
            "_claims_detail": [],
            "_all_runs": [{"details": [
                {"dimension": "relevance", "reason": "切题"},
                {"dimension": "format", "reason": "Markdown 规范"},
            ], "summary": "总体优秀"}],
        }

    def test_主观维理由取自details(self):
        scores, summary = build_optimized_scores(self._judge_result())
        assert scores["relevance"]["reason"] == "切题"
        assert scores["relevance"]["name"] == "相关性"
        assert summary == "总体优秀"

    def test_忠实度理由非空且含命中率(self):
        scores, _ = build_optimized_scores(self._judge_result())
        reason = scores["faithfulness"]["reason"]
        assert reason, "忠实度理由不得为空串"
        assert "5/10" in reason and scores["faithfulness"]["name"] == "忠实度"

    def test_平均分为算术均值且置顶(self):
        scores, _ = build_optimized_scores(self._judge_result())
        assert list(scores)[0] == "average"
        assert scores["average"] == 4.7  # (5*6 + 3.0) / 7 = 4.714 → 4.7

    def test_七维齐全无多余键(self):
        scores, _ = build_optimized_scores(self._judge_result())
        assert set(scores) - {"average"} == set(ALL_JUDGE_DIMENSIONS)

    def test_降级维度分数为None不回退0(self):
        r = self._judge_result()
        r["faithfulness"] = None
        scores, _ = build_optimized_scores(r)
        assert scores["faithfulness"]["score"] is None, "降级维度是未评估，不得写成 0 分"


class TestEnvironmentSelection:
    """环境切换：BASE_URL 手动覆盖 > environments.yaml 当前环境，且报错要说清缺什么。"""

    def test_BASE_URL手动覆盖优先并去尾部斜杠(self, monkeypatch):
        c = Config()
        monkeypatch.setenv("BASE_URL", "http://manual.local/restapi/")
        assert c.base_url == "http://manual.local/restapi"

    def test_未覆盖时取yaml当前环境(self, monkeypatch):
        c = Config()
        monkeypatch.delenv("BASE_URL", raising=False)
        c._current_env = "prod"
        expected = yaml.safe_load(
            (PROJECT_ROOT / "config" / "environments.yaml").read_text(encoding="utf-8")
        )["environments"]["prod"]["base_url"]
        assert c.base_url == expected.rstrip("/")

    def test_当前环境缺base_url时报错给出两条修法(self, monkeypatch):
        c = Config()
        monkeypatch.delenv("BASE_URL", raising=False)
        c._env_config = {"environments": {"ghost": {"description": "无地址"}}}
        c._current_env = "ghost"
        with pytest.raises(ConfigError) as exc:
            _ = c.base_url
        msg = str(exc.value)
        assert "ghost" in msg and "environments.yaml" in msg and "BASE_URL" in msg

    def test_切到未知环境时列出可用环境(self):
        c = Config()
        c._env_config = {"environments": {"pre": {"base_url": "x", "description": "预发"}}}
        with pytest.raises(ConfigError) as exc:
            c.switch_env("prod")
        assert "prod" in str(exc.value) and "pre" in str(exc.value), "报错要列出可用环境供纠正"

    def test_环境名优先级_环境变量高于yaml(self, monkeypatch):
        monkeypatch.setenv("TEST_ENV", " test ")  # 带空白也应可用
        assert _resolve_env_name() == "test"

    def test_yaml占位符形式回退prod(self, monkeypatch, tmp_path):
        """default_env 支持 "${TEST_ENV:-prod}" 写法；本函数不解析 shell 变量，取固定默认值。"""
        monkeypatch.delenv("TEST_ENV", raising=False)
        f = tmp_path / "environments.yaml"
        f.write_text('default_env: "${TEST_ENV:-prod}"\nenvironments: {}\n', encoding="utf-8")
        monkeypatch.setattr(config_module, "ENVIRONMENTS_FILE", f)
        assert _resolve_env_name() == "prod"

    def test_yaml显式默认环境被采用(self, monkeypatch, tmp_path):
        monkeypatch.delenv("TEST_ENV", raising=False)
        f = tmp_path / "environments.yaml"
        f.write_text("default_env: pre\nenvironments: {}\n", encoding="utf-8")
        monkeypatch.setattr(config_module, "ENVIRONMENTS_FILE", f)
        assert _resolve_env_name() == "pre"

    def test_yaml缺失时使用内置兜底(self, monkeypatch, tmp_path):
        monkeypatch.delenv("TEST_ENV", raising=False)
        monkeypatch.setattr(config_module, "ENVIRONMENTS_FILE", tmp_path / "not_exist.yaml")
        assert _resolve_env_name() == "prod"
