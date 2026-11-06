"""
Agent 行为测试薄壳引擎 — 委托 pytest 执行 SSE/LLM 行为用例（薄壳模式）。

设计模式：薄壳委托（Thin Shell）+ 模板方法（BaseEngine 子类）
职责：不自身实现任何测试逻辑，仅负责——
    1. 将框架 TestCase 翻译为 pytest node id；
    2. 以 subprocess 批量运行 test-cases/agent/ 下的 pytest 用例；
    3. 解析 junit.xml 将结果收口为框架 TestResult（含评分制字段）；
    4. 经 JSONReporter 产出 Layer 2 契约产物 artifacts/{engine}/{run_id}/summary.json。

为什么批量执行（覆盖 run() 而非逐用例 subprocess）：
    agent-test 资产的登录 Token、Langfuse 句柄等均为 pytest session 级 fixture，
    且 pytest-xdist 并行要求单一进程；逐用例拉起 subprocess 会导致每条用例
    重复登录/重复初始化，成本不可接受。execute_case() 仍保留实现，
    供调度器单独调某一用例的场景使用。

红线：pytest hook（conftest.py）保持原生机制，不重写为 EventBus 监听器。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...core.models import (
    TargetSystem,
    TestCase,
    TestMetrics,
    TestPlan,
    TestReport,
    TestResult,
)
from ...core.models.enums import TestStatus, TestType
from ..base import BaseEngine
from .config_schema import get_defaults
from .summary_writer import write_engine_summary

logger = logging.getLogger(__name__)

# 引擎标识（与 TestType 枚举值一致），产物路径 artifacts/{ENGINE}/... 使用
ENGINE = "agent_behavior"


class AgentBehaviorEngine(BaseEngine):
    """
    Agent 行为测试薄壳引擎。

    Attributes:
        _cfg: 归一化后的引擎配置（默认值 + 传入配置合并）。
        _run_id: 本次运行 ID（{YYYY-MM-DD}_{HHMMSS}_{6位短哈希}）。
        _artifacts_dir: 本次运行的 Layer 1/Layer 2 产物目录。
    """

    def __init__(self, config: Dict[str, Any], container: Any) -> None:
        """
        初始化引擎。

        Args:
            config: 引擎配置字典。兼容两种形态：完整配置（含顶层
                'agent_behavior' 键，来自 ConfigManager defaults 合并结果）
                或直接传 agent_behavior 段本身。
            container: IoC 容器实例。
        """
        raw = config.get(ENGINE, config) if isinstance(config, dict) else {}
        merged = {**get_defaults(), **raw}
        super().__init__(config=merged, container=container)
        self._cfg: Dict[str, Any] = merged
        self._run_id: str = ""
        self._artifacts_dir: Optional[Path] = None

    @property
    def engine_type(self) -> TestType:
        """返回 AGENT_BEHAVIOR 测试类型。"""
        return TestType.AGENT_BEHAVIOR

    # ── 模板方法覆盖：批量委托 ─────────────────────────────

    async def run(self, plan: TestPlan, target: TargetSystem) -> TestReport:
        """
        执行计划 — 一次 pytest subprocess 跑完全部用例。

        流程与 BaseEngine.run() 对齐（validate → setup → execute →
        metrics → report → teardown），仅把"逐用例循环"替换为
        "批量执行 + 查表收口"，原因见模块 docstring。

        Args:
            plan: 测试计划。
            target: 被测目标系统。

        Returns:
            测试报告（并落盘 Layer 2 summary.json）。
        """
        logger.info(f"引擎 {ENGINE} 开始执行，计划: {plan.name}")
        self.validate_config()
        await self.setup(target)

        try:
            cases = [c for suite in plan.suites for c in suite.get_all_cases()]
            self._results = await self._run_batch(cases)

            metrics = await self.collect_metrics()
            report = await self.generate_report(plan, metrics)

            # Layer 2 契约产物：无论成败都写，聚合器按 run_id 找文件
            await self._write_summary(plan)

            logger.info(f"引擎 {ENGINE} 执行完成，报告裁定: {report.verdict}")
            return report

        finally:
            await self.teardown()
            logger.info(f"引擎 {ENGINE} 资源已清理")

    # ── BaseEngine 抽象步骤实现 ────────────────────────────

    def validate_config(self) -> None:
        """
        校验引擎配置关键字段。

        Raises:
            ValueError: executor 非 pytest、timeout 非法或用例目录缺失。
        """
        executor = self._cfg.get("executor", "pytest")
        if executor != "pytest":
            raise ValueError(f"agent_behavior 仅支持 executor=pytest，当前: {executor}")
        timeout = self._cfg.get("pytest", {}).get("timeout", 1800)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError(f"pytest.timeout 必须为正数，当前: {timeout}")
        cases_dir = Path(self._cfg.get("cases_dir", "test-cases/agent"))
        if not cases_dir.is_dir():
            raise ValueError(f"用例目录不存在: {cases_dir}")

    async def setup(self, target: TargetSystem) -> None:
        """
        分配 run_id 并创建产物目录（artifacts/{ENGINE}/{run_id}/）。

        Args:
            target: 被测目标系统（透传为环境变量供 pytest 用例使用）。
        """
        self._run_id = self._cfg.get("run_id") or self._new_run_id()
        # 必须落为绝对路径：pytest 子进程的 cwd 是 cases_dir，
        # 相对 junit 路径会在子进程基准下解析导致父子进程路径错位
        self._artifacts_dir = (Path("artifacts") / ENGINE / self._run_id).resolve()
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"run_id={self._run_id} 产物目录={self._artifacts_dir}")

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        """
        独立执行单个用例（批量路径经由 run()，不走此方法）。

        Args:
            case: 测试用例（config 须含 node_id）。
            target: 被测目标系统。

        Returns:
            测试结果。
        """
        results = await self._run_batch([case])
        return results[0]

    async def collect_metrics(self) -> TestMetrics:
        """
        汇总本次运行的用例统计与平均评分。

        Returns:
            测试指标（total/passed/failed/... + custom.avg_score）。
        """
        counter = {
            TestStatus.PASS: 0, TestStatus.FAIL: 0,
            TestStatus.SKIP: 0, TestStatus.ERROR: 0,
        }
        for r in self._results:
            counter[r.status] = counter.get(r.status, 0) + 1
        scores = [r.score for r in self._results if r.score is not None]
        duration = sum(r.duration for r in self._results)
        custom: Dict[str, Any] = {}
        if scores:
            custom["avg_score"] = round(sum(scores) / len(scores), 4)
            custom["scored_cases"] = len(scores)
        return TestMetrics(
            total_cases=len(self._results),
            passed_cases=counter.get(TestStatus.PASS, 0),
            failed_cases=counter.get(TestStatus.FAIL, 0),
            skipped_cases=counter.get(TestStatus.SKIP, 0),
            errored_cases=counter.get(TestStatus.ERROR, 0),
            duration=round(duration, 3),
            custom=custom,
        )

    async def teardown(self) -> None:
        """清理产物目录引用（pytest 子进程自管资源，此处无长驻对象）。"""
        pass

    # ── 批量执行与解析 ─────────────────────────────────────

    async def _run_batch(self, cases: List[TestCase]) -> List[TestResult]:
        """
        一次 pytest subprocess 执行全部用例并收口结果。

        Args:
            cases: 待执行用例列表（config.node_id 为 pytest node id）。

        Returns:
            与入参顺序一致的测试结果列表。
        """
        if self._artifacts_dir is None:
            await self.setup(TargetSystem(id="", name=""))
        assert self._artifacts_dir is not None

        cases_dir = Path(self._cfg.get("cases_dir", "test-cases/agent"))
        node_ids = [c.config.get("node_id") for c in cases if c.config.get("node_id")]
        junit_path = self._artifacts_dir / "junit.xml"
        cmd = self._build_pytest_command(node_ids or None, str(junit_path))

        env = os.environ.copy()
        env["AGENT_TARGET_URL"] = str(self._cfg.get("target_url", ""))

        started = time.monotonic()
        proc = await asyncio.to_thread(
            subprocess.run,
            cmd,
            cwd=str(cases_dir),
            capture_output=True,
            text=True,
            timeout=self._cfg.get("pytest", {}).get("timeout", 1800),
            env=env,
        )
        elapsed = time.monotonic() - started
        logger.info(
            f"pytest 退出码={proc.returncode} 耗时={elapsed:.1f}s 输出尾行: "
            f"{(proc.stdout or '').strip().splitlines()[-1] if (proc.stdout or '').strip() else '(空)'}"
        )

        parsed = self._parse_junit(junit_path, cases, started)
        return self._merge_missing(parsed, cases, proc)

    def _build_pytest_command(
        self,
        node_ids: Optional[List[str]],
        junit_path: str,
    ) -> List[str]:
        """
        拼装 pytest 命令行（纯函数，便于单测）。

        Args:
            node_ids: 指定的用例 node id 列表；None 表示全量跑 cases_dir。
            junit_path: junit.xml 输出路径。

        Returns:
            subprocess 参数列表。
        """
        py = self._cfg.get("pytest", {})
        cmd = [sys.executable, "-m", "pytest"]
        cmd.extend(["--junitxml", junit_path, "-p", "no:cacheprovider"])
        markers = py.get("markers") or []
        if markers:
            cmd.extend(["-m", " or ".join(markers)])
        if py.get("use_xdist"):
            cmd.extend(["-n", "auto"])
        cmd.extend(py.get("extra_args") or [])
        cmd.extend(node_ids or ["."])
        return cmd

    def _parse_junit(
        self,
        junit_path: Path,
        cases: List[TestCase],
        started: float,
    ) -> Dict[str, TestResult]:
        """
        解析 junit.xml 为 case_id → TestResult 映射。

        评分字段约定：用例侧（judge 夹具）通过 pytest-junit 的
        <properties> 写入 score / threshold / dimensions(JSON)，
        薄壳只做搬运与归一化，不在此实现任何评分逻辑。

        Args:
            junit_path: junit.xml 路径。
            cases: 原始用例列表（提供 node_id → case_id 映射）。
            started: 批量执行开始时刻（monotonic），用于兜底耗时。

        Returns:
            case_id → TestResult；junit 缺失或解析失败时返回空映射。
        """
        results: Dict[str, TestResult] = {}
        if not junit_path.is_file():
            logger.warning(f"junit.xml 不存在: {junit_path}（pytest 可能整体崩溃）")
            return results
        try:
            root = ET.parse(str(junit_path)).getroot()
        except ET.ParseError as exc:
            logger.warning(f"junit.xml 解析失败: {exc}")
            return results

        node_to_case = {
            c.config.get("node_id"): c for c in cases if c.config.get("node_id")
        }
        for tc in root.iter("testcase"):
            case = self._match_case(tc, node_to_case)
            if case is None:
                # junit 里有多余条目（如全量跑时未计划内的用例），忽略并留日志
                logger.debug(f"junit 条目未匹配到计划用例，跳过: {tc.get('classname')}::{tc.get('name')}")
                continue
            results[case.id] = self._to_result(case, tc)
        return results

    @staticmethod
    def _match_case(tc: ET.Element, node_to_case: Dict[str, TestCase]) -> Optional[TestCase]:
        """
        按多种 nodeid 形态将 junit 条目匹配回计划用例。

        pytest 各 family/version 的 junit 属性不一致（实测 pytest 9 xunit2
        不写 file 属性），因此逐候选匹配：
            1. file::name（xunit1 形态）
            2. classname 点路径 → 斜杠路径.py::name（函数式，含包目录）
            3. pkg/mod.py::Cls::name（类方法式）

        Args:
            tc: junit testcase 元素。
            node_to_case: node_id → 用例映射。

        Returns:
            匹配到的用例，未匹配返回 None。
        """
        name = tc.get("name", "")
        candidates: List[str] = []
        file_attr = tc.get("file")
        if file_attr:
            candidates.append(f"{file_attr}::{name}")
        classname = tc.get("classname", "")
        if classname:
            parts = classname.split(".")
            candidates.append("/".join(parts) + f".py::{name}")
            if len(parts) >= 2:
                candidates.append("/".join(parts[:-1]) + f".py::{parts[-1]}::{name}")
        for key in candidates:
            case = node_to_case.get(key)
            if case is not None:
                return case
        return None

    def _to_result(self, case: TestCase, tc: ET.Element) -> TestResult:
        """
        将单个 <testcase> 元素转换为 TestResult。

        Args:
            case: 原始用例。
            tc: junit testcase XML 元素。

        Returns:
            测试结果（含评分制字段）。
        """
        status, message = TestStatus.PASS, ""
        if tc.find("skipped") is not None:
            status = TestStatus.SKIP
            message = (tc.find("skipped").get("message") or "")  # type: ignore[union-attr]
        elif tc.find("failure") is not None:
            status = TestStatus.FAIL
            message = (tc.find("failure").get("message") or "")[:500]  # type: ignore[union-attr]
        elif tc.find("error") is not None:
            status = TestStatus.ERROR
            message = (tc.find("error").get("message") or "")[:500]  # type: ignore[union-attr]

        score: Optional[float] = None
        threshold: Optional[float] = None
        dimensions: Dict[str, float] = {}
        props = tc.find("properties")
        if props is not None:
            for prop in props.findall("property"):
                name, value = prop.get("name", ""), prop.get("value", "")
                if name == "score":
                    score = _to_float(value)
                elif name == "threshold":
                    threshold = _to_float(value)
                elif name == "dimensions":
                    dimensions = _to_dims(value)

        # 未声明阈值的评分类用例回退引擎级默认阈值
        if score is not None and threshold is None:
            threshold = float(self._cfg.get("scoring", {}).get("default_threshold", 0.75))

        try:
            duration = float(tc.get("time", 0) or 0)
        except ValueError:
            duration = 0.0

        return TestResult(
            case_id=case.id,
            status=status,
            duration=duration,
            message=message,
            details={
                "node_id": case.config.get("node_id", ""),
                "classname": tc.get("classname", ""),
            },
            score=score,
            dimensions=dimensions,
            threshold=threshold,
        )

    def _merge_missing(
        self,
        parsed: Dict[str, TestResult],
        cases: List[TestCase],
        proc: "subprocess.CompletedProcess[str]",
    ) -> List[TestResult]:
        """
        为 junit 中缺失的用例补 ERROR 结果，保证与入参 cases 一一对应。

        Args:
            parsed: 已解析结果映射。
            cases: 原始用例列表。
            proc: pytest 进程对象（提供崩溃原因摘要）。

        Returns:
            完整结果列表（顺序同 cases）。
        """
        outputs: List[TestResult] = []
        tail = ""
        for stream in (proc.stderr, proc.stdout):
            lines = (stream or "").strip().splitlines()
            if lines:
                tail = lines[-1][:200]
                break
        for case in cases:
            if case.id in parsed:
                outputs.append(parsed[case.id])
            else:
                outputs.append(TestResult(
                    case_id=case.id,
                    status=TestStatus.ERROR,
                    message=f"junit 中无该用例执行记录（node_id={case.config.get('node_id')!r}）。{tail}",
                ))
        return outputs

    async def _write_summary(self, plan: TestPlan) -> None:
        """
        经 JSONReporter 唯一出口产出 Layer 2 summary.json。

        Args:
            plan: 测试计划（提供 plan_name）。
        """
        paths = await write_engine_summary(
            plan_name=plan.name,
            results=self._results,
            run_id=self._run_id,
            engine=ENGINE,
        )
        logger.info(f"Layer 2 产物已落盘: {paths['summary_path']}")

    @staticmethod
    def _new_run_id() -> str:
        """生成运行 ID：{YYYY-MM-DD}_{HHMMSS}_{6位短哈希}（命名规范约定）。"""
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return f"{stamp}_{secrets.token_hex(3)}"


def _to_float(value: str) -> Optional[float]:
    """junit property 字符串转 float，非法值返回 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_dims(value: str) -> Dict[str, float]:
    """解析 dimensions property（JSON 对象字符串），非法值返回空字典。"""
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    dims = {}
    for k, v in data.items():
        f = _to_float(str(v))
        if f is not None:
            dims[str(k)] = f
    return dims
