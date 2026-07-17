"""
Python 监控器 — 通过 psutil 或 Prometheus 采集 Python 进程指标。

职责：采集 Python 进程的 CPU、内存、GC 统计等运行时指标。
"""
from __future__ import annotations

import gc
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PythonMonitor:
    """
    Python 进程监控器。

    通过 psutil 采集指定进程的 CPU/内存指标，
    同时采集当前进程的 GC 统计信息。
    """

    async def collect(self, pid: Optional[int] = None) -> Dict[str, Any]:
        """
        采集 Python 进程指标。

        Args:
            pid: 目标进程 ID，默认为当前进程。

        Returns:
            Python 进程指标字典。
        """
        metrics: Dict[str, Any] = {}

        # 采集 psutil 进程指标
        try:
            import psutil
            target_pid = pid or os.getpid()
            process = psutil.Process(target_pid)

            cpu_percent = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()

            metrics["cpu_percent"] = cpu_percent
            metrics["memory_rss_mb"] = memory_info.rss / (1024 * 1024)
            metrics["memory_vms_mb"] = memory_info.vms / (1024 * 1024)
            metrics["num_threads"] = process.num_threads()
            metrics["num_fds"] = process.num_fds() if hasattr(process, "num_fds") else -1
        except ImportError:
            metrics["cpu_percent"] = -1
        except Exception as e:
            logger.warning(f"psutil 采集失败: {e}")

        # 采集 GC 统计
        gc_stats = gc.get_stats()
        metrics["gc_collections"] = sum(s.get("collections", 0) for s in gc_stats)
        metrics["gc_collected"] = sum(s.get("collected", 0) for s in gc_stats)
        metrics["gc_uncollectable"] = sum(s.get("uncollectable", 0) for s in gc_stats)

        return metrics
