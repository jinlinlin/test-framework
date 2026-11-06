"""
AgentBehaviorEngine 薄壳引擎单元测试。

覆盖：构造契约 / 配置校验 / pytest 命令拼装 / junit 解析收口 /
缺失用例补 ERROR / Layer 2 summary.json 落盘 / 真实 subprocess 端到端。

异步统一用 asyncio.run() 驱动（与本仓测试惯例一致）。
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_framework.core.models import TestCase, TestPlan, TestResult, TestSuite, TargetSystem
from test_framework.core.models.enums import TestStatus, TestType
from test_framework.engines.agent_behavior.engine import AgentBehaviorEngine
from test_framework.engines.agent_behavior.summary_writer import write_engine_summary
from test_framework.engines.engine_factory import EngineFactory


def _make_config(cases_dir: Path) -> dict:
    """构造指向临时用例目录的最小引擎配置（顶层 agent_behavior 段形态）。"""
    return {"agent_behavior": {"cases_dir": str(cases_dir)}}


def _make_case(case_id: str, node_id: str) -> TestCase:
    """构造带 pytest node_id 的用例。"""
    return TestCase(
        id=case_id,
        name=f"用例 {case_id}",
        test_type=TestType.AGENT_BEHAVIOR,
        target="uniplore",
        config={"node_id": node_id},
    )


@pytest.fixture
def agent_cases_dir(tmp_path: Path) -> Path:
    """生成含两个通过、一个失败用例的真实 pytest 目录。"""
    d = tmp_path / "cases"
    d.mkdir()
    (d / "test_demo.py").write_text(
        "def test_alpha():\n    assert True\n\n"
        "def test_beta():\n    assert 1 == 1\n\n"
        "def test_gamma():\n    assert False, '评分未达标'\n",
        encoding="utf-8",
    )
    return d


class TestEngineCreation:
    """构造契约：(config, container) 依赖注入，与其余引擎一致。"""

    def test_engine_creation_via_factory(self, agent_cases_dir, mock_container):
        engine = EngineFactory.create(
            TestType.AGENT_BEHAVIOR, _make_config(agent_cases_dir), mock_container,
        )
        assert isinstance(engine, AgentBehaviorEngine)
        assert engine.engine_type == TestType.AGENT_BEHAVIOR

    def test_engine_creation_accepts_bare_section(self, agent_cases_dir, mock_container):
        # 直接传 agent_behavior 段子集（不带顶层键）也应归一化成功
        engine = AgentBehaviorEngine(
            config={"cases_dir": str(agent_cases_dir)}, container=mock_container,
        )
        # 默认配置兜底：未提供 pytest 段时合并 config_schema 默认值
        assert engine._cfg["pytest"]["timeout"] == 1800
        assert engine._cfg["scoring"]["default_threshold"] == 0.75


class TestValidateConfig:
    """配置校验的失败路径。"""

    def test_rejects_missing_cases_dir(self, tmp_path, mock_container):
        engine = AgentBehaviorEngine(
            config={"cases_dir": str(tmp_path / "nonexistent")}, container=mock_container,
        )
        with pytest.raises(ValueError, match="用例目录不存在"):
            engine.validate_config()

    def test_rejects_non_pytest_executor(self, agent_cases_dir, mock_container):
        engine = AgentBehaviorEngine(
            config={"cases_dir": str(agent_cases_dir), "executor": "jest"},
            container=mock_container,
        )
        with pytest.raises(ValueError, match="executor=pytest"):
            engine.validate_config()


class TestBuildPytestCommand:
    """命令拼装纯函数：markers / xdist / extra_args / node 选择。"""

    def _engine(self, agent_cases_dir, mock_container, pytest_cfg):
        cfg = {"cases_dir": str(agent_cases_dir), "pytest": pytest_cfg}
        return AgentBehaviorEngine(config=cfg, container=mock_container)

    def test_full_flags(self, agent_cases_dir, mock_container):
        engine = self._engine(agent_cases_dir, mock_container, {
            "markers": ["rag", "smoke"],
            "use_xdist": True,
            "extra_args": ["--reruns", "1"],
        })
        cmd = engine._build_pytest_command(["test_x.py::test_y"], "j.xml")
        assert cmd[0] == sys.executable
        assert cmd[1:3] == ["-m", "pytest"]
        assert "--junitxml" in cmd and "j.xml" in cmd
        # 注意 "-m" 在 "python -m pytest" 与 marker 两处出现，只验 marker 表达式在列
        assert "rag or smoke" in cmd
        assert "-n" in cmd and "auto" in cmd
        assert "--reruns" in cmd
        assert cmd[-1] == "test_x.py::test_y"

    def test_no_node_ids_runs_directory(self, agent_cases_dir, mock_container):
        engine = self._engine(agent_cases_dir, mock_container, {})
        cmd = engine._build_pytest_command(None, "j.xml")
        assert cmd[-1] == "."


class TestJunitParsing:
    """junit.xml → TestResult 收口，含评分制 properties。"""

    JUNIT_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4">
  <testcase file="test_demo.py" classname="test_demo" name="test_alpha" time="1.2"/>
  <testcase file="test_demo.py" classname="test_demo" name="test_beta" time="0.3">
    <failure message="AssertionError: 评分未达标">detail</failure>
  </testcase>
  <testcase file="test_demo.py" classname="test_demo" name="test_gamma" time="0.0">
    <skipped message="需要环境 pre"/>
  </testcase>
  <testcase file="test_demo.py" classname="test_demo" name="test_scored" time="2.0">
    <properties>
      <property name="score" value="0.82"/>
      <property name="dimensions" value='{"relevance": 0.9, "depth": 0.74}'/>
    </properties>
  </testcase>
</testsuite></testsuites>
"""

    @pytest.fixture
    def junit_file(self, tmp_path: Path) -> Path:
        p = tmp_path / "junit.xml"
        p.write_text(self.JUNIT_XML, encoding="utf-8")
        return p

    def _parse(self, junit_file, cases, agent_cases_dir, mock_container):
        engine = AgentBehaviorEngine(
            config={"cases_dir": str(agent_cases_dir)}, container=mock_container,
        )
        return engine._parse_junit(junit_file, cases, started=0.0)

    def test_status_mapping_and_missing_properties(self, junit_file, agent_cases_dir, mock_container):
        cases = [
            _make_case("c1", "test_demo.py::test_alpha"),
            _make_case("c2", "test_demo.py::test_beta"),
            _make_case("c3", "test_demo.py::test_gamma"),
        ]
        parsed = self._parse(junit_file, cases, agent_cases_dir, mock_container)
        assert parsed["c1"].status == TestStatus.PASS
        assert parsed["c1"].duration == pytest.approx(1.2)
        assert parsed["c2"].status == TestStatus.FAIL
        assert "评分未达标" in parsed["c2"].message
        assert parsed["c3"].status == TestStatus.SKIP

    def test_score_fields_and_default_threshold(self, junit_file, agent_cases_dir, mock_container):
        cases = [_make_case("c4", "test_demo.py::test_scored")]
        parsed = self._parse(junit_file, cases, agent_cases_dir, mock_container)
        r = parsed["c4"]
        assert r.score == pytest.approx(0.82)
        assert r.dimensions == {"relevance": 0.9, "depth": 0.74}
        # 未声明 threshold 时回退引擎默认阈值 0.75，0.82 >= 0.75 判通过
        assert r.threshold == pytest.approx(0.75)
        assert r.passed_by_score is True

    def test_merge_missing_produces_error(self, agent_cases_dir, mock_container):
        engine = AgentBehaviorEngine(
            config={"cases_dir": str(agent_cases_dir)}, container=mock_container,
        )
        cases = [_make_case("c1", "test_demo.py::test_alpha"), _make_case("cX", "test_demo.py::test_ghost")]
        proc = SimpleNamespace(stdout="INTERNALERROR boom", stderr="")
        outputs = engine._merge_missing({}, cases, proc)
        assert [o.case_id for o in outputs] == ["c1", "cX"]
        assert all(o.status == TestStatus.ERROR for o in outputs)
        assert "INTERNALERROR" in outputs[0].message


class TestSummaryWriter:
    """Layer 2 出口：TestResult 枚举值词表必须被 JSONReporter 正确计数。"""

    def test_summary_counts_enum_status_values(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        results = [
            TestResult(case_id="c1", status=TestStatus.PASS, score=0.9, threshold=0.75),
            TestResult(case_id="c2", status=TestStatus.FAIL, message="未达标"),
            TestResult(case_id="c3", status=TestStatus.ERROR, message="崩溃"),
        ]
        paths = asyncio.run(write_engine_summary(
            plan_name="agent回归", results=results, run_id="run-1", engine="agent_behavior",
        ))
        summary_file = tmp_path / paths["summary_path"]
        assert summary_file.is_file()
        data = json.loads(summary_file.read_text(encoding="utf-8"))
        assert data["schema_version"] == "1.0"
        assert data["engine"] == "agent_behavior"
        assert data["totals"]["passed"] == 1
        assert data["totals"]["failed"] == 1
        assert data["totals"]["errors"] == 1
        assert {f["case_id"] for f in data["failures"]} == {"c2", "c3"}


class TestEndToEnd:
    """真实拉起 pytest 子进程跑通 run() 全流程（A′-4 的预演）。"""

    def test_run_executes_pytest_and_emits_summary(self, agent_cases_dir, mock_container, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        engine = AgentBehaviorEngine(config=_make_config(agent_cases_dir), container=mock_container)
        plan = TestPlan(
            id="plan-e2e",
            name="端到端冒烟",
            suites=[TestSuite(
                id="s1", name="demo",
                children=[
                    _make_case("c_alpha", "test_demo.py::test_alpha"),
                    _make_case("c_beta", "test_demo.py::test_beta"),
                    _make_case("c_gamma", "test_demo.py::test_gamma"),
                ],
            )],
        )
        target = TargetSystem(id="uniplore", name="UniResearch 预发", base_url="http://example.invalid")

        report = asyncio.run(engine.run(plan, target))

        assert report.summary["total"] == 3
        assert report.summary["passed"] == 2
        assert report.summary["failed"] == 1
        assert engine._run_id  # setup 已分配运行 ID

        summary_file = Path("artifacts") / "agent_behavior" / engine._run_id / "summary.json"
        assert summary_file.is_file()
        data = json.loads(summary_file.read_text(encoding="utf-8"))
        assert data["totals"]["passed"] == 2
        assert data["totals"]["failed"] == 1
