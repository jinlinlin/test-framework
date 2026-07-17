"""
Grafana 推送器 — 将测试指标推送到 Grafana（通过 InfluxDB 数据源）。

特点：
- 通过 InfluxDB Line Protocol 推送时序数据
- 支持自定义标签和测量名称
- 兼容 Grafana Dashboard 可视化
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GrafanaPusher:
    """
    Grafana 指标推送器。

    通过 InfluxDB HTTP API 将测试指标写入时序数据库，
    Grafana 通过 InfluxDB 数据源展示。

    配置::

        pusher = GrafanaPusher(
            influx_url="http://localhost:8086",
            database="test_metrics",
            measurement="test_results",
        )
    """

    def __init__(
        self,
        influx_url: str = "http://localhost:8086",
        database: str = "test_metrics",
        measurement: str = "test_results",
        username: str = "",
        password: str = "",
    ) -> None:
        """
        Args:
            influx_url: InfluxDB 服务地址。
            database: 数据库名称。
            measurement: 测量名称。
            username: 用户名（可选）。
            password: 密码（可选）。
        """
        self._influx_url = influx_url.rstrip("/")
        self._database = database
        self._measurement = measurement
        self._username = username
        self._password = password

    async def push(
        self,
        metrics: Dict[str, float],
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        推送指标到 InfluxDB。

        Args:
            metrics: 指标名称→值的映射。
            tags: 标签字典（用于 Grafana 过滤和分组）。
            timestamp: 时间戳（默认为当前时间）。
        """
        import aiohttp

        ts = timestamp or time.time()
        ts_ns = int(ts * 1e9)

        # 构建 InfluxDB Line Protocol
        tag_str = ""
        if tags:
            tag_str = "," + ",".join(f"{k}={v}" for k, v in tags.items())

        field_str = ",".join(f"{k}={v}" for k, v in metrics.items())
        line = f"{self._measurement}{tag_str} {field_str} {ts_ns}"

        # 写入 InfluxDB
        write_url = f"{self._influx_url}/write?db={self._database}"
        auth = None
        if self._username:
            auth = aiohttp.BasicAuth(self._username, self._password)

        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(write_url, data=line) as resp:
                if resp.status not in (200, 204):
                    text = await resp.text()
                    logger.error(f"InfluxDB 写入失败 ({resp.status}): {text}")
                else:
                    logger.debug(f"指标已推送到 Grafana: {len(metrics)} 项")

    async def push_batch(
        self,
        metrics_list: List[Dict[str, float]],
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """批量推送指标。"""
        import aiohttp

        lines = []
        for metrics in metrics_list:
            tag_str = ""
            if tags:
                tag_str = "," + ",".join(f"{k}={v}" for k, v in tags.items())
            field_str = ",".join(f"{k}={v}" for k, v in metrics.items())
            ts_ns = int(time.time() * 1e9)
            lines.append(f"{self._measurement}{tag_str} {field_str} {ts_ns}")

        body = "\n".join(lines)
        write_url = f"{self._influx_url}/write?db={self._database}"

        async with aiohttp.ClientSession() as session:
            async with session.post(write_url, data=body) as resp:
                if resp.status not in (200, 204):
                    logger.error(f"InfluxDB 批量写入失败: {resp.status}")
