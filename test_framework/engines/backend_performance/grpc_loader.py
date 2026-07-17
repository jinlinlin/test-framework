"""
gRPC 负载发生器 — 对 gRPC 服务施加并发负载。

职责：基于 grpcio 实现 gRPC 调用的并发负载施压，
      采集延迟、吞吐量和错误率指标。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class GRPCLoader:
    """
    gRPC 负载发生器。

    通过 grpcio 对 gRPC 服务施加并发调用负载。

    Attributes:
        _config: gRPC 配置。
        _target: 被测目标系统。
    """

    def __init__(self, config: Dict[str, Any], target: Any) -> None:
        """
        初始化 gRPC 负载发生器。

        Args:
            config: gRPC 配置（proto_file, service, method 等）。
            target: 被测目标系统。
        """
        self._config = config
        self._target = target
        self._host = getattr(target, "host", "localhost")
        self._port = getattr(target, "port", 50051)

    async def apply_load(self, case_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 gRPC 负载测试。

        Args:
            case_config: 用例级别的配置。

        Returns:
            负载测试结果字典。
        """
        concurrency = case_config.get("concurrency", self._config.get("concurrency", 50))
        duration = case_config.get("duration", self._config.get("duration", 60))
        service = case_config.get("service", self._config.get("service", ""))
        method = case_config.get("method", self._config.get("method", ""))

        logger.info(f"开始 gRPC 负载测试: {service}/{method}, 并发={concurrency}")

        latencies: List[float] = []
        success_count = 0
        fail_count = 0
        start_time = time.time()
        end_time = start_time + duration

        try:
            import grpc

            # 创建 gRPC channel
            channel = grpc.aio.insecure_channel(f"{self._host}:{self._port}")

            while time.time() < end_time:
                tasks = [
                    self._invoke_rpc(channel, service, method, case_config)
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

            await channel.close()

        except ImportError:
            logger.error("grpcio 未安装，请运行: pip install grpcio")
            return {"error": "grpcio 未安装"}

        total_time = time.time() - start_time
        total_requests = success_count + fail_count

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

    async def _invoke_rpc(
        self, channel: Any, service: str, method: str, case_config: Dict
    ) -> Dict[str, Any]:
        """
        执行单次 gRPC RPC 调用。

        Args:
            channel: gRPC 异步 channel。
            service: 服务名。
            method: 方法名。
            case_config: 用例配置。

        Returns:
            调用结果。
        """
        start = time.time()
        try:
            # 使用 UnaryUnary 通用调用
            request = case_config.get("request_body", {})
            rpc_method = f"/{service}/{method}"
            response = await channel.unary_unary(
                rpc_method,
                request_serializer=lambda x: str(x).encode(),
                response_deserializer=lambda x: x,
            )(request)
            latency = (time.time() - start) * 1000
            return {"success": True, "latency": latency}
        except Exception as e:
            return {"success": False, "latency": 0, "error": str(e)}

    @staticmethod
    def _percentile(sorted_data: List[float], pct: float) -> float:
        """计算百分位数。"""
        if not sorted_data:
            return 0
        k = (len(sorted_data) - 1) * (pct / 100)
        f = int(k)
        c = min(f + 1, len(sorted_data) - 1)
        return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])
