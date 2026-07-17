"""
查询执行器 — 执行 SQL 查询并统计性能指标。

职责：从连接池获取连接执行查询，支持单次执行和基准测试模式，
      自动统计延迟、吞吐量、百分位数等性能指标。
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """
    基准测试结果。

    Attributes:
        total_time: 总耗时（秒）。
        avg_time: 平均耗时（毫秒）。
        p50: 第 50 百分位数（毫秒）。
        p95: 第 95 百分位数（毫秒）。
        p99: 第 99 百分位数（毫秒）。
        qps: 每秒查询数。
        errors: 错误次数。
        total_queries: 总查询次数。
    """

    total_time: float = 0.0
    avg_time: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    qps: float = 0.0
    errors: int = 0
    total_queries: int = 0


class QueryExecutor:
    """
    查询执行器。

    从连接池获取连接，执行 SQL 查询并收集性能指标。
    支持单次执行和基准测试（多轮迭代 + 并发）。

    Attributes:
        _pool: 数据库连接池。
        _dialect: 数据库方言。
    """

    def __init__(self, pool: Any, dialect: Any) -> None:
        """
        初始化查询执行器。

        Args:
            pool: ConnectionPool 实例。
            dialect: Dialect 实例。
        """
        self._pool = pool
        self._dialect = dialect

    async def execute(self, query: str, params: Any = None) -> Any:
        """
        执行单次查询。

        从连接池获取连接，执行查询后归还连接。

        Args:
            query: SQL 查询语句。
            params: 查询参数。

        Returns:
            查询结果。
        """
        conn = await self._pool.acquire()
        try:
            result = await self._dialect.execute_query(conn, query, params)
            return result
        finally:
            await self._pool.release(conn)

    async def execute_benchmark(
        self,
        query: str,
        iterations: int = 100,
        concurrency: int = 1,
        params: Any = None,
    ) -> BenchmarkResult:
        """
        执行基准测试。

        重复执行查询指定次数，支持并发执行，
        统计延迟分布和吞吐量指标。

        Args:
            query: SQL 查询语句。
            iterations: 迭代次数。
            concurrency: 并发数（1 为串行）。
            params: 查询参数。

        Returns:
            基准测试结果。
        """
        durations: List[float] = []
        errors: int = 0
        start_total = time.monotonic()

        if concurrency <= 1:
            # 串行执行
            for i in range(iterations):
                elapsed, err = await self._execute_once(query, params)
                durations.append(elapsed)
                if err:
                    errors += 1
        else:
            # 并发执行
            semaphore = asyncio.Semaphore(concurrency)
            tasks = []

            async def _run_once() -> None:
                async with semaphore:
                    elapsed, err = await self._execute_once(query, params)
                    durations.append(elapsed)
                    if err:
                        nonlocal errors
                        errors += 1

            for _ in range(iterations):
                tasks.append(_run_once())
            await asyncio.gather(*tasks)

        total_time = time.monotonic() - start_total

        # 计算统计指标
        return self._calculate_metrics(durations, errors, total_time, iterations)

    async def _execute_once(self, query: str, params: Any = None) -> tuple:
        """
        执行单次查询并测量耗时。

        Args:
            query: SQL 查询。
            params: 查询参数。

        Returns:
            (耗时毫秒, 是否出错) 元组。
        """
        conn = await self._pool.acquire()
        try:
            start = time.monotonic()
            await self._dialect.execute_query(conn, query, params)
            elapsed_ms = (time.monotonic() - start) * 1000
            return elapsed_ms, False
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.debug(f"查询执行出错: {e}")
            return elapsed_ms, True
        finally:
            await self._pool.release(conn)

    def _calculate_metrics(
        self,
        durations: List[float],
        errors: int,
        total_time: float,
        iterations: int,
    ) -> BenchmarkResult:
        """
        计算基准测试统计指标。

        Args:
            durations: 每次查询耗时列表（毫秒）。
            errors: 错误次数。
            total_time: 总耗时（秒）。
            iterations: 迭代次数。

        Returns:
            基准测试结果。
        """
        if not durations:
            return BenchmarkResult(
                total_time=total_time,
                total_queries=iterations,
                errors=errors,
            )

        sorted_d = sorted(durations)
        n = len(sorted_d)

        avg_time = sum(sorted_d) / n
        p50 = sorted_d[int(n * 0.50)]
        p95 = sorted_d[int(n * 0.95)]
        p99 = sorted_d[min(int(n * 0.99), n - 1)]
        qps = n / total_time if total_time > 0 else 0

        return BenchmarkResult(
            total_time=total_time,
            avg_time=round(avg_time, 3),
            p50=round(p50, 3),
            p95=round(p95, 3),
            p99=round(p99, 3),
            qps=round(qps, 2),
            errors=errors,
            total_queries=iterations,
        )
