"""
负载发生器适配器统一接口。

职责：定义负载测试工具的统一抽象，
      包含场景配置、执行、结果收集等方法。
      支持 JMeter / Locust / k6 三种负载测试工具。
"""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..base import BaseAdapter


@dataclass
class LoadTestScenario:
    """
    负载测试场景配置。

    Attributes:
        name: 场景名称。
        target_url: 目标 URL。
        method: HTTP 方法。
        headers: 请求头。
        body: 请求体。
        virtual_users: 虚拟用户数。
        ramp_up_seconds: 爬升时间（秒）。
        duration_seconds: 持续时间（秒）。
        think_time_ms: 思考时间（毫秒）。
        extra_params: 额外参数。
    """

    name: str = "default"
    target_url: str = ""
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    virtual_users: int = 10
    ramp_up_seconds: int = 10
    duration_seconds: int = 60
    think_time_ms: int = 0
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadTestResult:
    """
    负载测试结果。

    Attributes:
        total_requests: 总请求数。
        successful_requests: 成功请求数。
        failed_requests: 失败请求数。
        error_rate: 错误率（0-1）。
        avg_response_time_ms: 平均响应时间（毫秒）。
        p50_response_time_ms: 50 分位响应时间。
        p90_response_time_ms: 90 分位响应时间。
        p95_response_time_ms: 95 分位响应时间。
        p99_response_time_ms: 99 分位响应时间。
        min_response_time_ms: 最小响应时间。
        max_response_time_ms: 最大响应时间。
        requests_per_second: 每秒请求数（QPS）。
        throughput_bytes: 吞吐量（字节）。
        duration_seconds: 实际执行时间（秒）。
        raw_data: 原始数据（工具特定格式）。
        errors: 错误信息列表。
    """

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0
    avg_response_time_ms: float = 0.0
    p50_response_time_ms: float = 0.0
    p90_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    min_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    requests_per_second: float = 0.0
    throughput_bytes: int = 0
    duration_seconds: float = 0.0
    raw_data: Any = None
    errors: List[Dict[str, Any]] = field(default_factory=list)


class LoadGeneratorAdapter(BaseAdapter):
    """
    负载发生器适配器抽象基类。

    定义负载测试场景配置、执行、结果收集等统一方法。
    """

    @property
    def adapter_type(self) -> str:
        return "load_generator"

    @abstractmethod
    async def run_test(self, scenario: LoadTestScenario) -> LoadTestResult:
        """
        执行负载测试。

        Args:
            scenario: 测试场景配置。

        Returns:
            测试结果。
        """
        ...

    @abstractmethod
    async def validate_scenario(self, scenario: LoadTestScenario) -> List[str]:
        """
        验证测试场景配置是否合法。

        Args:
            scenario: 测试场景配置。

        Returns:
            错误信息列表（空列表表示合法）。
        """
        ...

    @abstractmethod
    async def get_supported_features(self) -> Dict[str, bool]:
        """
        获取当前负载工具支持的功能。

        Returns:
            功能名称→是否支持的映射。
            如: {"websocket": True, "grpc": False, "ramp_up": True}
        """
        ...

    @abstractmethod
    async def generate_config_file(
        self,
        scenario: LoadTestScenario,
        output_path: str,
    ) -> str:
        """
        生成负载工具的配置文件。

        Args:
            scenario: 测试场景配置。
            output_path: 输出文件路径。

        Returns:
            生成的配置文件路径。
        """
        ...
