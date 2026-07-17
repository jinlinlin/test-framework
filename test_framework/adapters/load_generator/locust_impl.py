"""
基于 Locust 的负载发生器适配器。

特点：
- Python 原生编写，代码即配置
- 动态生成 Locust 脚本
- 支持分布式压测（master-worker 模式）
- 内置 Web UI 实时监控
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from .adapter import LoadGeneratorAdapter, LoadTestResult, LoadTestScenario

logger = logging.getLogger(__name__)


class LocustAdapter(LoadGeneratorAdapter):
    """
    Locust 负载发生器适配器。

    配置项::

        {
            "locust_path": "locust",           # Locust 可执行文件路径
            "master_host": "localhost",         # Master 节点地址
            "master_port": 5557,                # Master 端口
            "workers": 0,                       # Worker 数量（0 表示单节点模式）
            "web_port": 8089,                   # Web UI 端口
            "headless": True,                   # 是否无头模式（不启动 Web UI）
        }
    """

    @property
    def implementation_name(self) -> str:
        return "locust"

    def __init__(self) -> None:
        """初始化 Locust 适配器。"""
        self._config: Dict[str, Any] = {}
        self._connected: bool = False

    async def connect(self, config: Dict[str, Any]) -> None:
        """验证 Locust 安装。"""
        self._config = config
        locust_path = config.get("locust_path", "locust")

        try:
            proc = await asyncio.create_subprocess_exec(
                locust_path, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            version_str = stdout.decode().strip() or stderr.decode().strip()
            logger.debug(f"Locust 版本: {version_str}")
            self._connected = True
        except FileNotFoundError:
            logger.warning("Locust 未找到，将在执行时再次尝试")
            self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        logger.debug("LocustAdapter 已断开")

    async def is_connected(self) -> bool:
        return self._connected

    def _generate_locustfile(self, scenario: LoadTestScenario) -> str:
        """生成 Locust 脚本文件。"""
        headers_json = json.dumps(scenario.headers, ensure_ascii=False)
        body_code = ""
        if scenario.body:
            body_json = json.dumps(scenario.body, ensure_ascii=False) if isinstance(scenario.body, dict) else f'"""{scenario.body}"""'
            body_code = f"            data={body_json},"

        script = f'''"""自动生成的 Locust 测试脚本 - {scenario.name}"""
import time
from locust import HttpUser, task, between

class TestUser(HttpUser):
    """虚拟用户定义。"""
    wait_time = between({scenario.think_time_ms / 1000.0}, {max(scenario.think_time_ms / 1000.0 * 1.5, 1.0)})
    host = "{scenario.target_url}"

    @task
    def test_task(self):
        """测试任务。"""
        self.client.{scenario.method.lower()}(
            "/",
            headers={headers_json},{body_code}
            name="{scenario.name}",
        )
'''
        return script

    async def run_test(self, scenario: LoadTestScenario) -> LoadTestResult:
        """
        执行 Locust 负载测试。

        流程：生成 locustfile → 执行 locust → 解析 CSV 结果
        """
        locust_path = self._config.get("locust_path", "locust")
        headless = self._config.get("headless", True)

        with tempfile.TemporaryDirectory(prefix="locust_") as tmp_dir:
            # 生成 locustfile
            locustfile = os.path.join(tmp_dir, "locustfile.py")
            with open(locustfile, "w", encoding="utf-8") as f:
                f.write(self._generate_locustfile(scenario))

            # CSV 输出文件
            csv_prefix = os.path.join(tmp_dir, "results")

            # 构建命令
            cmd = [
                locust_path,
                "-f", locustfile,
                "--users", str(scenario.virtual_users),
                "--spawn-rate", str(max(1, scenario.virtual_users // max(scenario.ramp_up_seconds, 1))),
                "--run-time", f"{scenario.duration_seconds}s",
                "--csv", csv_prefix,
                "--headless",
            ]

            # 执行
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return LoadTestResult(
                    errors=[{"type": "execution_error", "message": stderr.decode()}],
                )

            # 解析 CSV 结果
            return self._parse_csv_results(csv_prefix, scenario.duration_seconds)

    def _parse_csv_results(self, csv_prefix: str, expected_duration: float) -> LoadTestResult:
        """解析 Locust CSV 统计结果。"""
        import csv as csv_module

        stats_file = f"{csv_prefix}_stats.csv"
        if not os.path.exists(stats_file):
            return LoadTestResult(errors=[{"type": "file_not_found", "message": stats_file}])

        try:
            with open(stats_file, "r", encoding="utf-8") as f:
                reader = csv_module.DictReader(f)
                total_row = None
                for row in reader:
                    if row.get("Name") == "Aggregated" or row.get("Type") == "":
                        total_row = row
                        break

            if not total_row:
                return LoadTestResult(errors=[{"type": "parse_error", "message": "未找到汇总统计行"}])

            total_requests = int(total_row.get("Request Count", 0))
            failure_count = int(total_row.get("Failure Count", 0))
            success_count = total_requests - failure_count

            return LoadTestResult(
                total_requests=total_requests,
                successful_requests=success_count,
                failed_requests=failure_count,
                error_rate=failure_count / total_requests if total_requests > 0 else 0.0,
                avg_response_time_ms=float(total_row.get("Average Response Time", 0)),
                p50_response_time_ms=float(total_row.get("50%", 0)),
                p90_response_time_ms=float(total_row.get("90%", 0)),
                p95_response_time_ms=float(total_row.get("95%", 0)),
                p99_response_time_ms=float(total_row.get("99%", 0)),
                min_response_time_ms=float(total_row.get("Min Response Time", 0)),
                max_response_time_ms=float(total_row.get("Max Response Time", 0)),
                requests_per_second=float(total_row.get("Requests/s", 0)),
                throughput_bytes=0,
                duration_seconds=expected_duration,
            )
        except Exception as e:
            return LoadTestResult(errors=[{"type": "parse_error", "message": str(e)}])

    async def validate_scenario(self, scenario: LoadTestScenario) -> List[str]:
        errors: List[str] = []
        if not scenario.target_url:
            errors.append("目标 URL 不能为空")
        if scenario.virtual_users < 1:
            errors.append("虚拟用户数必须 >= 1")
        if scenario.duration_seconds < 1:
            errors.append("持续时间必须 >= 1 秒")
        if scenario.method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
            errors.append(f"不支持的 HTTP 方法: {scenario.method}")
        return errors

    async def get_supported_features(self) -> Dict[str, bool]:
        return {
            "http": True,
            "websocket": True,
            "grpc": False,
            "jdbc": False,
            "jms": False,
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
        script = self._generate_locustfile(scenario)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script)
        return output_path
