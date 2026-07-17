"""
数据库性能测试引擎 — 引擎主类。

职责：数据库性能测试主引擎，管理连接池、执行查询、
      分析执行计划、生成索引建议、采集性能指标。
      支持 PostgreSQL / MySQL / MongoDB / Redis。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ...core.models import TestCase, TestMetrics, TestResult, TargetSystem
from ...core.models.enums import TestStatus, TestType
from ..base import BaseEngine
from .connection_pool import ConnectionPool
from .dialect.base import DialectFactory
from .explain_analyzer import ExplainAnalyzer
from .index_advisor import IndexAdvisor
from .query_executor import QueryExecutor

logger = logging.getLogger(__name__)


class DatabaseEngine(BaseEngine):
    """
    数据库性能测试引擎。

    执行流程：建立连接池 → 执行查询基准测试 → 分析执行计划 →
    生成索引建议 → 采集性能指标 → 生成报告。

    Attributes:
        _dialect: 数据库方言实例。
        _pool: 连接池管理器。
        _executor: 查询执行器。
        _explain_analyzer: 执行计划分析器。
        _index_advisor: 索引建议器。
    """

    @property
    def engine_type(self) -> TestType:
        """引擎类型。"""
        return TestType.DATABASE

    async def setup(self, target: TargetSystem) -> None:
        """
        初始化数据库引擎。

        创建方言实例、连接池、查询执行器、分析器、建议器。

        Args:
            target: 目标系统对象，config 中需包含数据库连接参数。
        """
        # 获取数据库类型
        target_config = getattr(target, "config", {}) or {}
        db_type = target_config.get("db_type", "postgresql")

        # 创建方言
        self._dialect = DialectFactory.create(db_type)
        logger.info(f"数据库方言: {self._dialect.name}")

        # 创建连接池
        pool_config = self._config.get("pool", {})
        self._pool = ConnectionPool(self._dialect, pool_config)
        await self._pool.initialize(target)

        # 创建查询执行器
        self._executor = QueryExecutor(self._pool, self._dialect)

        # 创建执行计划分析器
        self._explain_analyzer = ExplainAnalyzer(self._pool, self._dialect)

        # 创建索引建议器
        advisor_config = self._config.get("index_advisor", {})
        self._index_advisor = IndexAdvisor(self._dialect, advisor_config)

        logger.info(f"数据库引擎已初始化: type={db_type}")

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        """
        执行单个数据库性能测试用例。

        流程：执行查询基准测试 → 可选执行计划分析 → 可选索引建议。

        用例配置格式::

            {
                "query": "SELECT * FROM users WHERE age > 18",
                "iterations": 100,
                "concurrency": 1,
                "explain": true,
                "index_advice": true
            }

        Args:
            case: 测试用例对象。
            target: 目标系统对象。

        Returns:
            测试结果。
        """
        try:
            query = case.config.get("query", "")
            iterations = case.config.get("iterations", 100)
            concurrency = case.config.get("concurrency", 1)
            do_explain = case.config.get("explain", self._config.get("query", {}).get("explain", False))
            do_advice = case.config.get("index_advice", self._config.get("query", {}).get("index_advice", False))

            if not query:
                return TestResult(
                    case_id=case.id,
                    status=TestStatus.FAIL,
                    duration=0,
                    details={"error": "查询语句不能为空"},
                    metrics=TestMetrics(),
                    timestamp=datetime.now(),
                )

            # 1. 执行基准测试
            bench_result = await self._executor.execute_benchmark(
                query, iterations=iterations, concurrency=concurrency
            )

            # 2. 执行计划分析（可选）
            explain_result = None
            if do_explain:
                explain_result = await self._explain_analyzer.analyze(query)

            # 3. 索引建议（可选）
            suggestions = []
            if do_advice and explain_result:
                suggestions = self._index_advisor.analyze(explain_result)

            # 确定测试状态
            status = TestStatus.PASS
            if bench_result.errors > iterations * 0.1:  # 超过 10% 错误率
                status = TestStatus.FAIL

            # 构建详情
            details: Dict[str, Any] = {
                "benchmark": {
                    "total_time": bench_result.total_time,
                    "avg_time_ms": bench_result.avg_time,
                    "p50_ms": bench_result.p50,
                    "p95_ms": bench_result.p95,
                    "p99_ms": bench_result.p99,
                    "qps": bench_result.qps,
                    "errors": bench_result.errors,
                },
            }

            if explain_result:
                details["explain"] = explain_result

            if suggestions:
                details["index_suggestions"] = suggestions

            # 连接池统计
            details["pool_stats"] = self._pool.stats()

            return TestResult(
                case_id=case.id,
                status=status,
                duration=bench_result.total_time,
                details=details,
                metrics=TestMetrics(
                    latency_avg=bench_result.avg_time,
                    latency_p50=bench_result.p50,
                    latency_p95=bench_result.p95,
                    latency_p99=bench_result.p99,
                    throughput=bench_result.qps,
                ),
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"数据库测试异常: {e}")
            return TestResult(
                case_id=case.id,
                status=TestStatus.ERROR,
                duration=0,
                details={"error": str(e)},
                metrics=TestMetrics(),
                timestamp=datetime.now(),
            )

    async def collect_metrics(self) -> TestMetrics:
        """汇总数据库测试指标。"""
        if not self._results:
            return TestMetrics()

        avg_latency = sum(r.metrics.latency_avg for r in self._results) / len(self._results)
        total_throughput = sum(r.metrics.throughput for r in self._results)

        return TestMetrics(
            total_cases=len(self._results),
            passed=sum(1 for r in self._results if r.status == TestStatus.PASS),
            failed=sum(1 for r in self._results if r.status == TestStatus.FAIL),
            latency_avg=avg_latency,
            throughput=total_throughput,
        )

    async def teardown(self) -> None:
        """关闭连接池和数据库引擎。"""
        if hasattr(self, "_pool") and self._pool:
            await self._pool.close()
            logger.info("数据库引擎已关闭")
