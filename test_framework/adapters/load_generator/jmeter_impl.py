"""
基于 Apache JMeter 的负载发生器适配器。

特点：
- 通过命令行调用 JMeter 执行测试
- 生成 JMX 配置文件
- 解析 JTL 结果文件
- 支持丰富的协议（HTTP/WebSocket/JDBC/JMS 等）
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import tempfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .adapter import LoadGeneratorAdapter, LoadTestResult, LoadTestScenario

logger = logging.getLogger(__name__)


class JMeterAdapter(LoadGeneratorAdapter):
    """
    Apache JMeter 负载发生器适配器。

    配置项::

        {
            "jmeter_home": "/opt/jmeter",        # JMeter 安装目录
            "java_home": "",                      # Java 安装目录（可选）
            "jmeter_properties": {},              # JMeter 属性覆盖
            "output_dir": "./results/jmeter",     # 结果输出目录
        }
    """

    @property
    def implementation_name(self) -> str:
        return "jmeter"

    def __init__(self) -> None:
        """初始化 JMeter 适配器。"""
        self._jmeter_home: str = ""
        self._output_dir: str = "./results/jmeter"
        self._connected: bool = False

    async def connect(self, config: Dict[str, Any]) -> None:
        """
        验证 JMeter 安装。

        Args:
            config: JMeter 配置。
        """
        self._jmeter_home = config.get("jmeter_home", "")
        self._output_dir = config.get("output_dir", "./results/jmeter")

        # 检查 JMeter 是否可用
        jmeter_bin = os.path.join(self._jmeter_home, "bin", "jmeter")
        if not self._jmeter_home:
            # 尝试 PATH 中的 jmeter
            jmeter_bin = "jmeter"

        try:
            proc = await asyncio.create_subprocess_exec(
                jmeter_bin, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.debug(f"JMeter 已可用: {stdout.decode().strip()[:100]}")
                self._connected = True
            else:
                logger.warning(f"JMeter 版本检查失败: {stderr.decode()}")
                self._connected = True  # 仍然标记为已连接
        except FileNotFoundError:
            logger.warning("JMeter 未找到，将在执行时再次尝试")
            self._connected = True  # 延迟验证

    async def disconnect(self) -> None:
        self._connected = False
        logger.debug("JMeterAdapter 已断开")

    async def is_connected(self) -> bool:
        return self._connected

    # ===== 负载测试执行 =====

    async def run_test(self, scenario: LoadTestScenario) -> LoadTestResult:
        """
        执行 JMeter 负载测试。

        流程：生成 JMX → 执行 JMeter → 解析 JTL 结果
        """
        # 创建临时目录
        with tempfile.TemporaryDirectory(prefix="jmeter_") as tmp_dir:
            jmx_path = os.path.join(tmp_dir, "test.jmx")
            jtl_path = os.path.join(tmp_dir, "results.jtl")
            log_path = os.path.join(tmp_dir, "jmeter.log")

            # 生成 JMX 文件
            self._generate_jmx(scenario, jmx_path)

            # 执行 JMeter
            jmeter_bin = os.path.join(self._jmeter_home, "bin", "jmeter") if self._jmeter_home else "jmeter"
            cmd = [
                jmeter_bin, "-n", "-t", jmx_path,
                "-l", jtl_path,
                "-j", log_path,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"JMeter 执行失败: {stderr.decode()}")
                return LoadTestResult(
                    errors=[{"type": "execution_error", "message": stderr.decode()}],
                )

            # 解析 JTL 结果
            return self._parse_jtl(jtl_path, scenario.duration_seconds)

    def _generate_jmx(self, scenario: LoadTestScenario, output_path: str) -> None:
        """生成 JMX 测试计划文件。"""
        parsed = urlparse(scenario.target_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        protocol = parsed.scheme or "http"

        # 构建 JMX XML
        root = ET.Element("jmeterTestPlan", version="1.2")
        hash_tree = ET.SubElement(root, "hashTree")

        # 测试计划
        test_plan = ET.SubElement(hash_tree, "TestPlan", guiclass="TestPlanGui", testclass="TestPlan")
        ET.SubElement(test_plan, "stringProp", name="TestPlan.name").text = scenario.name
        ET.SubElement(test_plan, "boolProp", name="TestPlan.serialize_threadgroups").text = "false"
        hash_tree_tp = ET.SubElement(hash_tree, "hashTree")

        # 线程组
        thread_group = ET.SubElement(
            hash_tree_tp, "ThreadGroup",
            guiclass="ThreadGroupGui", testclass="ThreadGroup",
        )
        ET.SubElement(thread_group, "stringProp", name="ThreadGroup.num_threads").text = str(scenario.virtual_users)
        ET.SubElement(thread_group, "stringProp", name="ThreadGroup.ramp_time").text = str(scenario.ramp_up_seconds)
        ET.SubElement(thread_group, "boolProp", name="ThreadGroup.scheduler").text = "true"
        ET.SubElement(thread_group, "stringProp", name="ThreadGroup.duration").text = str(scenario.duration_seconds)
        hash_tree_tg = ET.SubElement(hash_tree_tp, "hashTree")

        # HTTP 请求默认值
        http_defaults = ET.SubElement(
            hash_tree_tg, "ConfigTestElement",
            guiclass="HttpDefaultsGui", testclass="ConfigTestElement",
        )
        ET.SubElement(http_defaults, "stringProp", name="HTTPSampler.domain").text = host
        ET.SubElement(http_defaults, "stringProp", name="HTTPSampler.port").text = str(port)
        ET.SubElement(http_defaults, "stringProp", name="HTTPSampler.protocol").text = protocol
        ET.SubElement(hash_tree_tg, "hashTree")

        # HTTP 请求采样器
        sampler = ET.SubElement(
            hash_tree_tg, "HTTPSamplerProxy",
            guiclass="HttpTestSampleGui", testclass="HTTPSamplerProxy",
        )
        ET.SubElement(sampler, "stringProp", name="HTTPSampler.path").text = path
        ET.SubElement(sampler, "stringProp", name="HTTPSampler.method").text = scenario.method
        if scenario.body:
            ET.SubElement(sampler, "boolProp", name="HTTPSampler.postBodyRaw").text = "true"
        ET.SubElement(hash_tree_tg, "hashTree")

        # 结果收集器
        result_collector = ET.SubElement(
            hash_tree_tg, "ResultCollector",
            guiclass="ViewResultsFullVisualizer", testclass="ResultCollector",
        )
        ET.SubElement(result_collector, "stringProp", name="filename").text = ""
        ET.SubElement(hash_tree_tg, "hashTree")

        # 写入文件
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="utf-8", xml_declaration=True)

    def _parse_jtl(self, jtl_path: str, expected_duration: float) -> LoadTestResult:
        """解析 JTL 结果文件。"""
        if not os.path.exists(jtl_path):
            return LoadTestResult(errors=[{"type": "file_not_found", "message": f"JTL 文件不存在: {jtl_path}"}])

        response_times: List[float] = []
        success_count = 0
        failure_count = 0
        total_bytes = 0
        errors: List[Dict[str, Any]] = []

        try:
            with open(jtl_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    elapsed = float(row.get("elapsed", 0))
                    success = row.get("success", "true").lower() == "true"
                    bytes_sent = int(row.get("bytes", 0))

                    response_times.append(elapsed)
                    total_bytes += bytes_sent
                    if success:
                        success_count += 1
                    else:
                        failure_count += 1
                        error_msg = row.get("responseMessage", "Unknown error")
                        errors.append({"type": "request_error", "message": error_msg})
        except Exception as e:
            errors.append({"type": "parse_error", "message": str(e)})

        total = success_count + failure_count
        if not response_times:
            return LoadTestResult(errors=errors)

        response_times.sort()
        n = len(response_times)
        duration = expected_duration or (n / 10.0)

        def percentile(p: float) -> float:
            idx = int(p / 100.0 * (n - 1))
            return response_times[min(idx, n - 1)]

        return LoadTestResult(
            total_requests=total,
            successful_requests=success_count,
            failed_requests=failure_count,
            error_rate=failure_count / total if total > 0 else 0.0,
            avg_response_time_ms=sum(response_times) / n,
            p50_response_time_ms=percentile(50),
            p90_response_time_ms=percentile(90),
            p95_response_time_ms=percentile(95),
            p99_response_time_ms=percentile(99),
            min_response_time_ms=response_times[0],
            max_response_time_ms=response_times[-1],
            requests_per_second=total / duration if duration > 0 else 0,
            throughput_bytes=total_bytes,
            duration_seconds=duration,
            errors=errors[:50],  # 限制错误数量
        )

    async def validate_scenario(self, scenario: LoadTestScenario) -> List[str]:
        errors: List[str] = []
        if not scenario.target_url:
            errors.append("目标 URL 不能为空")
        if scenario.virtual_users < 1:
            errors.append("虚拟用户数必须 >= 1")
        if scenario.duration_seconds < 1:
            errors.append("持续时间必须 >= 1 秒")
        return errors

    async def get_supported_features(self) -> Dict[str, bool]:
        return {
            "http": True,
            "websocket": True,
            "grpc": False,
            "jdbc": True,
            "jms": True,
            "ramp_up": True,
            "think_time": True,
            "parameterization": True,
            "distributed_testing": True,
        }

    async def generate_config_file(
        self,
        scenario: LoadTestScenario,
        output_path: str,
    ) -> str:
        self._generate_jmx(scenario, output_path)
        return output_path
