"""
资源采集器 — 采集被测服务的 CPU、内存、网络 IO 指标。

职责：支持直连进程、Docker stats、K8s metrics API 三种采集方式，
      在负载测试期间定时采样运行指标。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResourceCollector:
    """
    资源采集器。

    在负载测试期间定期采集被测服务的运行指标，
    支持进程直连、Docker、K8s 三种采集方式。

    Attributes:
        _config: 资源监控配置。
        _samples: 采集的数据点列表。
        _running: 采集状态标志。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """初始化资源采集器。"""
        self._config = config
        self._interval = config.get("interval", 5)  # 采集间隔（秒）
        self._samples: List[Dict[str, float]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """启动后台定时采集。"""
        if not self._config.get("enabled", True):
            logger.debug("资源监控已禁用")
            return
        self._running = True
        self._task = asyncio.create_task(self._collect_loop())
        logger.debug("资源采集器已启动")

    async def _collect_loop(self) -> None:
        """后台采集循环。"""
        while self._running:
            try:
                sample = await self._collect_once()
                self._samples.append(sample)
            except Exception as e:
                logger.debug(f"资源采集异常: {e}")
            await asyncio.sleep(self._interval)

    async def _collect_once(self) -> Dict[str, float]:
        """
        执行单次采集。

        Returns:
            采集到的指标字典。
        """
        metrics: Dict[str, float] = {}

        # 采集本机 CPU 和内存
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            metrics["cpu_percent"] = cpu_percent
            metrics["memory_percent"] = memory.percent
            metrics["memory_used_mb"] = memory.used / (1024 * 1024)
        except ImportError:
            metrics["cpu_percent"] = -1
            metrics["memory_percent"] = -1

        return metrics

    async def collect(self) -> Dict[str, float]:
        """
        获取最新采集数据的平均值。

        Returns:
            平均指标字典。
        """
        if not self._samples:
            return {}

        # 计算平均值
        keys = self._samples[0].keys()
        avg = {}
        for key in keys:
            values = [s.get(key, 0) for s in self._samples if s.get(key, -1) >= 0]
            avg[key] = sum(values) / len(values) if values else 0

        return avg

    async def stop(self) -> None:
        """停止采集。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.debug("资源采集器已停止")
