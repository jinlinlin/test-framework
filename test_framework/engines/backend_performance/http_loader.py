"""
HTTP 负载发生器 — 对 HTTP 服务施加并发负载。

职责：支持 GET/POST/PUT/DELETE，可配置并发数和持续时间，
      输出延迟百分位、吞吐量、错误率等指标。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HTTPLoader:
    """
    HTTP 负载发生器。

    使用 httpx 异步客户端对目标 URL 施加并发请求，
    采集延迟百分位、吞吐量、错误率等指标。

    Attributes:
        _config: 引擎配置。
        _target: 被测目标系统。
    """

    def __init__(self, config: Dict[str, Any], target: Any) -> None:
        """
        初始化 HTTP 负载发生器。

        Args:
            config: 后端性能配置。
            target: 被测目标系统。
        """
        self._config = config
        self._target = target
        self._base_url = getattr(target, "base_url", "http://localhost")

    async def apply_load(self, case_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 HTTP 负载测试。

        Args:
            case_config: 用例级别的配置（path, method, concurrency, duration 等）。

        Returns:
            负载测试结果字典，包含：
            total_requests, success_count, fail_count,
            latency_avg, latency_p50, latency_p95, latency_p99,
            throughput, error_rate, duration
        """
        # 从用例配置获取参数
        path = case_config.get("path", "/")
        method = case_config.get("method", self._config.get("http", {}).get("method", "GET"))
        concurrency = case_config.get("concurrency", self._config.get("concurrency", 100))
        duration = case_config.get("duration", self._config.get("duration", 60))
        url = f"{self._base_url}{path}"

        logger.info(f"开始 HTTP 负载测试: {method} {url}, 并发={concurrency}, 持续={duration}s")

        # 执行并发请求
        latencies: List[float] = []
        success_count = 0
        fail_count = 0
        start_time = time.time()

        try:
            import httpx

            async with httpx.AsyncClient(
                timeout=self._config.get("http", {}).get("timeout", 30),
                verify=self._config.get("verify_ssl", True),
            ) as client:
                end_time = start_time + duration

                while time.time() < end_time:
                    # 创建一批并发任务
                    tasks = [
                        self._send_request(client, method, url, case_config)
                        for _ in range(concurrency)
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for result in results:
                        if isinstance(result, Exception):
                            fail_count += 1
                        elif result.get("success"):
                            success_count += 1
                            latencies.append(result["latency"])
                        else:
                            fail_count += 1

        except ImportError:
            logger.error("httpx 未安装，请运行: pip install httpx")
            return {"error": "httpx 未安装"}

        total_time = time.time() - start_time
        total_requests = success_count + fail_count

        # 计算统计指标
        latencies.sort()
        return {
            "total_requests": total_requests,
            "success_count": success_count,
            "fail_count": fail_count,
            "latency_avg": sum(latencies) / len(latencies) if latencies else 0,
            "latency_p50": self._percentile(latencies, 50),
            "latency_p95": self._percentile(latencies, 95),
            "latency_p99": self._percentile(latencies, 99),
            "throughput": success_count / total_time if total_time > 0 else 0,
            "error_rate": fail_count / total_requests if total_requests > 0 else 0,
            "duration": total_time,
        }

    async def _send_request(
        self, client: Any, method: str, url: str, case_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        发送单个 HTTP 请求。

        Args:
            client: httpx 异步客户端。
            method: HTTP 方法。
            url: 请求 URL。
            case_config: 用例配置。

        Returns:
            请求结果字典。
        """
        start = time.time()
        try:
            kwargs: Dict[str, Any] = {}
            if method.upper() in ("POST", "PUT", "PATCH"):
                kwargs["json"] = case_config.get("body", {})
            headers = case_config.get("headers", self._config.get("http", {}).get("headers", {}))
            if headers:
                kwargs["headers"] = headers

            response = await client.request(method.upper(), url, **kwargs)
            latency = (time.time() - start) * 1000  # 转换为毫秒

            return {
                "success": response.status_code < 400,
                "latency": latency,
                "status_code": response.status_code,
            }
        except Exception as e:
            return {"success": False, "latency": 0, "error": str(e)}

    @staticmethod
    def _percentile(sorted_data: List[float], pct: float) -> float:
        """
        计算百分位数。

        Args:
            sorted_data: 已排序的数据列表。
            pct: 百分位（0-100）。

        Returns:
            百分位值。
        """
        if not sorted_data:
            return 0
        k = (len(sorted_data) - 1) * (pct / 100)
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[f]
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])
