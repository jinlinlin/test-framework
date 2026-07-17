"""
容器监控器 — 采集 Docker/K8s 容器的 CPU、内存、网络 IO。

职责：通过 Docker API 或 K8s metrics API 采集容器运行指标。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ContainerMonitor:
    """
    容器监控器。

    支持 Docker stats 和 Kubernetes metrics API 两种采集方式。
    """

    async def collect_docker(self, container_id: str) -> Dict[str, Any]:
        """
        采集 Docker 容器指标。

        Args:
            container_id: Docker 容器 ID 或名称。

        Returns:
            容器指标字典。
        """
        try:
            import httpx
            # 通过 Docker socket API 获取 stats
            async with httpx.AsyncClient(
                transport=httpx.AsyncHTTPTransport(uds="/var/run/docker.sock")
            ) as client:
                response = await client.get(
                    f"http://localhost/containers/{container_id}/stats?stream=false",
                    timeout=10,
                )
                data = response.json()

                # 解析 CPU 使用率
                cpu_stats = data.get("cpu_stats", {})
                cpu_delta = (
                    cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                    - data.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                )
                system_delta = (
                    cpu_stats.get("system_cpu_usage", 0)
                    - data.get("precpu_stats", {}).get("system_cpu_usage", 0)
                )
                num_cpus = cpu_stats.get("online_cpus", 1)
                cpu_percent = (cpu_delta / system_delta * num_cpus * 100) if system_delta > 0 else 0

                # 解析内存使用
                memory_stats = data.get("memory_stats", {})
                memory_used = memory_stats.get("usage", 0)
                memory_limit = memory_stats.get("limit", 1)

                # 解析网络 IO
                networks = data.get("networks", {})
                rx_bytes = sum(n.get("rx_bytes", 0) for n in networks.values())
                tx_bytes = sum(n.get("tx_bytes", 0) for n in networks.values())

                return {
                    "cpu_percent": round(cpu_percent, 2),
                    "memory_used_mb": memory_used / (1024 * 1024),
                    "memory_limit_mb": memory_limit / (1024 * 1024),
                    "memory_percent": round(memory_used / memory_limit * 100, 2) if memory_limit else 0,
                    "network_rx_mb": rx_bytes / (1024 * 1024),
                    "network_tx_mb": tx_bytes / (1024 * 1024),
                }
        except Exception as e:
            logger.warning(f"Docker 指标采集失败: {e}")
            return {"error": str(e)}

    async def collect_k8s(
        self, pod_name: str, namespace: str = "default"
    ) -> Dict[str, Any]:
        """
        采集 Kubernetes Pod 指标。

        Args:
            pod_name: Pod 名称。
            namespace: Kubernetes 命名空间。

        Returns:
            Pod 指标字典。
        """
        try:
            import httpx
            # 通过 K8s metrics API 获取
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.get(
                    f"https://kubernetes.default.svc/apis/metrics.k8s.io/v1beta1/"
                    f"namespaces/{namespace}/pods/{pod_name}",
                    timeout=10,
                )
                data = response.json()

                containers = data.get("containers", [])
                if not containers:
                    return {"error": "未找到容器数据"}

                # 汇总所有容器的指标
                total_cpu = "0"
                total_memory = "0"
                for container in containers:
                    usage = container.get("usage", {})
                    total_cpu = usage.get("cpu", "0")
                    total_memory = usage.get("memory", "0")

                return {
                    "cpu": total_cpu,
                    "memory": total_memory,
                    "container_count": len(containers),
                }
        except Exception as e:
            logger.warning(f"K8s 指标采集失败: {e}")
            return {"error": str(e)}
