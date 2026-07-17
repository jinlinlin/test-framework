"""
基于 k6 的负载发生器适配器。

特点：
- JavaScript 脚本编写测试场景
- 高性能 VUs（虚拟用户）引擎
- 丰富的内置指标（VUs/iterations/duration/data_sent/data_received 等）
- 支持阈值（thresholds）自动判断通过/失败
- 支持 JSON/CSV/Prometheus 等多种输出格式
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


class K6Adapter(LoadGeneratorAdapter):
    """
    k6 负载发生器适配器。

    配置项::

        {
            "k6_path": "k6",                   # k6 可执行文件路径
            "output_format": "json",            # 输出格式（json / csv）
            "cloud_token": "",                  # k6 Cloud token（可选）
            "tags": {},                         # 全局标签
            "thresholds": {                     # 性能阈值
                "http_req_duration": ["p(95)<500"],
                "http_req_failed": ["rate<0.01"],
            },
        }
    """

    @property
    def implementation_name(self) -> str:
        return "k6"

    def __init__(self) -> None:
        """初始化 k6 适配器。"""
        self._config: Dict[str, Any] = {}
        self._connected: bool = False

    async def connect(self, config: Dict[str, Any]) -> None:
        """验证 k6 安装。"""
        self._config = config
        k6_path = config.get("k6_path", "k6")

        try:
            proc = await asyncio.create_subprocess_exec(
                k6_path, "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            version_str = stdout.decode().strip()
            logger.debug(f"k6 版本: {version_str}")
            self._connected = True
        except FileNotFoundError:
            logger.warning("k6 未找到，将在执行时再次尝试")
            self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        logger.debug("K6Adapter 已断开")

    async def is_connected(self) -> bool:
        return self._connected

    def _generate_k6_script(self, scenario: LoadTestScenario) -> str:
        """生成 k6 JavaScript 测试脚本。"""
        thresholds = self._config.get("thresholds", {
            "http_req_duration": ["p(95)<3000"],
            "http_req_failed": ["rate<0.1"],
        })
        thresholds_json = json.dumps(thresholds, ensure_ascii=False)

        headers_json = json.dumps(scenario.headers, ensure_ascii=False)

        # 请求体
        body_code = "null"
        if scenario.body:
            if isinstance(scenario.body, dict):
                body_code = f"JSON.stringify({json.dumps(scenario.body)})"
            else:
                body_code = f"`{scenario.body}`"

        method = scenario.method.upper()
        request_code = ""
        if method in ("POST", "PUT", "PATCH"):
            request_code = f"""
    const response = http.{method.lower()}(
      "{scenario.target_url}",
      {body_code},
      {{ headers: {headers_json} }}
    );"""
        else:
            request_code = f"""
    const response = http.{method.lower()}(
      "{scenario.target_url}",
      {{ headers: {headers_json} }}
    );"""

        think_time = scenario.think_time_ms / 1000.0 if scenario.think_time_ms > 0 else 0.5

        script = f"""// 自动生成的 k6 测试脚本 - {scenario.name}
import http from 'k6/http';
import {{ check, sleep }} from 'k6';

// 性能阈值
export const options = {{
  vus: {scenario.virtual_users},
  duration: '{scenario.duration_seconds}s',
  rampUp: {{
    type: 'ramping-vus',
    startVUs: 0,
    stages: [
      {{ duration: '{scenario.ramp_up_seconds}s', target: {scenario.virtual_users} }},
      {{ duration: '{max(scenario.duration_seconds - scenario.ramp_up_seconds, 1)}s', target: {scenario.virtual_users} }},
    ],
  }},
  thresholds: {thresholds_json},
}};

// 默认执行函数
export default function () {{{request_code}

    // 验证响应
    check(response, {{
      'status is 2xx': (r) => r.status >= 200 && r.status < 300,
      'response time < 2000ms': (r) => r.timings.duration < 2000,
    }});

    sleep({think_time});
}}
"""
        return script

    async def run_test(self, scenario: LoadTestScenario) -> LoadTestResult:
        """
        执行 k6 负载测试。

        流程：生成 JS 脚本 → 执行 k6 → 解析 JSON 输出
        """
        k6_path = self._config.get("k6_path", "k6")

        with tempfile.TemporaryDirectory(prefix="k6_") as tmp_dir:
            # 生成脚本
            script_path = os.path.join(tmp_dir, "script.js")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(self._generate_k6_script(scenario))

            # JSON 输出文件
            json_output = os.path.join(tmp_dir, "results.json")

            # 构建命令
            cmd = [
                k6_path, "run",
                "--out", f"json={json_output}",
                script_path,
            ]

            # 执行
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            stdout_text = stdout.decode()
            stderr_text = stderr.decode()

            if proc.returncode != 0:
                return LoadTestResult(
                    errors=[{"type": "execution_error", "message": stderr_text or stdout_text}],
                )

            # 解析结果（从 stdout 提取摘要）
            return self._parse_k6_output(stdout_text, json_output, scenario.duration_seconds)

    def _parse_k6_output(
        self,
        stdout_text: str,
        json_output: str,
        expected_duration: float,
    ) -> LoadTestResult:
        """解析 k6 标准输出中的摘要信息。"""
        import re

        result = LoadTestResult(duration_seconds=expected_duration)
        errors: List[Dict[str, Any]] = []

        # 从 stdout 中提取指标
        lines = stdout_text.strip().split("\n")
        for line in lines:
            line = line.strip()

            # http_req_duration
            match = re.search(r"http_req_duration[.]*\s+avg=([\d.]+)ms", line)
            if match:
                result.avg_response_time_ms = float(match.group(1))

            # http_req_duration p(95)
            match = re.search(r"p\(95\)=([\d.]+)ms", line)
            if match:
                result.p95_response_time_ms = float(match.group(1))

            # http_reqs
            match = re.search(r"http_reqs[.]*\s+([\d.]+)/s", line)
            if match:
                result.requests_per_second = float(match.group(1))

            # http_req_failed
            match = re.search(r"http_req_failed[.]*\s+([\d.]+)%", line)
            if match:
                result.error_rate = float(match.group(1)) / 100.0

            # iterations（总请求数）
            match = re.search(r"iterations[.]*\s+(\d+)\s+", line)
            if match:
                result.total_requests = int(match.group(1))

            # 阈值失败
            if "✗" in line or "failed" in line.lower():
                errors.append({"type": "threshold_failed", "message": line})

        # 计算衍生指标
        result.failed_requests = int(result.total_requests * result.error_rate)
        result.successful_requests = result.total_requests - result.failed_requests

        # 尝试读取 JSON 详细结果
        if os.path.exists(json_output):
            try:
                durations: List[float] = []
                with open(json_output, "r", encoding="utf-8") as f:
                    for json_line in f:
                        try:
                            entry = json.loads(json_line)
                            if entry.get("type") == "Point" and entry.get("metric") == "http_req_duration":
                                val = entry.get("data", {}).get("value", 0)
                                durations.append(val)
                        except json.JSONDecodeError:
                            continue

                if durations:
                    durations.sort()
                    n = len(durations)
                    result.avg_response_time_ms = sum(durations) / n
                    result.min_response_time_ms = durations[0]
                    result.max_response_time_ms = durations[-1]
                    result.p50_response_time_ms = durations[int(n * 0.5)]
                    result.p90_response_time_ms = durations[int(n * 0.9)]
                    result.p95_response_time_ms = durations[int(n * 0.95)]
                    result.p99_response_time_ms = durations[min(int(n * 0.99), n - 1)]
                    result.total_requests = n
            except Exception as e:
                errors.append({"type": "parse_error", "message": str(e)})

        result.errors = errors[:50]
        return result

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
            "grpc": True,
            "jdbc": False,
            "jms": False,
            "ramp_up": True,
            "think_time": True,
            "parameterization": True,
            "distributed_testing": False,  # k6 Cloud 支持
        }

    async def generate_config_file(
        self,
        scenario: LoadTestScenario,
        output_path: str,
    ) -> str:
        script = self._generate_k6_script(scenario)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script)
        return output_path
