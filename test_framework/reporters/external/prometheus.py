"""
Prometheus 推送器 — 将测试指标推送到 Prometheus Push Gateway。

特点：
- 通过 Prometheus Push Gateway 推送指标
- 支持 Gauge / Counter / Histogram 指标类型
- 兼容 Grafana + Prometheus 监控体系
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PrometheusPusher:
    """
    Prometheus Push Gateway 推送器。

    配置::

        pusher = PrometheusPusher(
            gateway="http://localhost:9091",
            job="test_framework",
        )
    """

    def __init__(
        self,
        gateway: str = "http://localhost:9091",
        job: str = "test_framework",
    ) -> None:
        """
        Args:
            gateway: Prometheus Push Gateway 地址。
            job: 作业名称（Prometheus 标签）。
        """
        self._gateway = gateway.rstrip("/")
        self._job = job

    async def push(
        self,
        metrics: Dict[str, float],
        grouping_key: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        推送指标到 Prometheus Push Gateway。

        Args:
            metrics: 指标名称→值的映射。
            grouping_key: 分组标签（如 instance, plan_name 等）。
        """
        import aiohttp

        # 构建 Prometheus exposition format
        lines = []
        for name, value in metrics.items():
            # Prometheus 指标名规范：[a-zA-Z_:][a-zA-Z0-9_:]*
            safe_name = name.replace("-", "_").replace(".", "_")
            lines.append(f"# TYPE {safe_name} gauge")
            lines.append(f"{safe_name} {value}")

        body = "\n".join(lines) + "\n"

        # 构建 URL
        url = f"{self._gateway}/metrics/job/{self._job}"
        if grouping_key:
            for k, v in grouping_key.items():
                url += f"/{k}/{v}"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=body,
                headers={"Content-Type": "text/plain; charset=utf-8"},
            ) as resp:
                if resp.status not in (200, 202):
                    text = await resp.text()
                    logger.error(f"Prometheus 推送失败 ({resp.status}): {text}")
                else:
                    logger.debug(f"指标已推送到 Prometheus: {len(metrics)} 项")

    async def delete(self, grouping_key: Optional[Dict[str, str]] = None) -> None:
        """删除 Push Gateway 中的指标。"""
        import aiohttp

        url = f"{self._gateway}/metrics/job/{self._job}"
        if grouping_key:
            for k, v in grouping_key.items():
                url += f"/{k}/{v}"

        async with aiohttp.ClientSession() as session:
            async with session.delete(url) as resp:
                if resp.status not in (200, 202):
                    logger.warning(f"Prometheus 指标删除失败: {resp.status}")
