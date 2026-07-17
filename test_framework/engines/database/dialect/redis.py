"""
Redis 方言 — 基于 aioredis / redis.asyncio 实现。

职责：处理 Redis 性能测试相关命令（INFO / SLOWLOG / LATENCY / DEBUG），
      提供连接管理和命令执行接口。
依赖：redis（延迟导入）
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .base import Dialect

logger = logging.getLogger(__name__)


class RedisDialect(Dialect):
    """
    Redis 方言实现。

    Redis 是 KV 存储，不使用 SQL，性能分析主要通过
    SLOWLOG（慢查询日志）、LATENCY（延迟监控）、INFO（服务器信息）等命令。

    Attributes:
        _client: Redis 异步客户端。
    """

    @property
    def name(self) -> str:
        """方言名称。"""
        return "redis"

    def build_explain_query(self, sql: str) -> str:
        """
        Redis 不使用 EXPLAIN，返回原始命令。

        性能分析通过 DEBUG OBJECT / SLOWLOG 等命令完成。

        Args:
            sql: Redis 命令字符串。

        Returns:
            原始命令。
        """
        return sql

    def parse_explain_result(self, result: Any) -> Dict[str, Any]:
        """
        解析 Redis 性能分析结果。

        输入为 DEBUG / SLOWLOG / LATENCY 等命令的综合结果。

        Args:
            result: 性能分析结果字典。

        Returns:
            统一格式的分析结果。
        """
        if not isinstance(result, dict):
            return {
                "plan_type": "unknown",
                "estimated_cost": 0,
                "estimated_rows": 0,
                "actual_rows": 0,
                "tables": [],
                "indexes_used": [],
                "warnings": [],
            }

        warnings: List[str] = []

        # 分析 SLOWLOG
        slowlog = result.get("slowlog", [])
        if slowlog:
            for entry in slowlog[:5]:  # 取前 5 条慢查询
                duration = entry.get("duration", 0)
                command = entry.get("command", "")
                if duration > 10000:  # > 10ms
                    warnings.append(f"慢查询: {command} 耗时 {duration}μs")

        # 分析 INFO 中的内存使用
        info = result.get("info", {})
        used_memory = info.get("used_memory_human", "0")
        mem_fragmentation = info.get("mem_fragmentation_ratio", 1.0)
        if isinstance(mem_fragmentation, (int, float)) and mem_fragmentation > 1.5:
            warnings.append(
                f"内存碎片率较高: {mem_fragmentation}，建议重启或整理"
            )

        # 分析 LATENCY
        latency = result.get("latency", {})
        avg_latency = latency.get("avg", 0)
        if avg_latency > 10:  # > 10ms
            warnings.append(f"平均延迟较高: {avg_latency}ms")

        return {
            "plan_type": "redis_command",
            "estimated_cost": avg_latency if isinstance(avg_latency, (int, float)) else 0,
            "estimated_rows": 0,
            "actual_rows": 0,
            "tables": [],
            "indexes_used": [],
            "warnings": warnings,
            "memory_usage": used_memory,
            "slowlog_count": len(slowlog),
        }

    def get_connection_string(self, config: Dict[str, Any]) -> str:
        """
        生成 Redis 连接字符串。

        Args:
            config: 连接配置字典。

        Returns:
            Redis URL。
        """
        host = config.get("host", "localhost")
        port = config.get("port", 6379)
        password = config.get("password", "")
        db = config.get("db", 0)

        if password:
            return f"redis://:{password}@{host}:{port}/{db}"
        return f"redis://{host}:{port}/{db}"

    async def create_connection(self, conn_str: str) -> Any:
        """
        创建 Redis 异步连接。

        Args:
            conn_str: Redis URL。

        Returns:
            Redis 客户端对象。
        """
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(conn_str, decode_responses=True)
            # 测试连接
            await client.ping()
            logger.debug(f"Redis 连接已创建")
            return client
        except ImportError:
            raise ImportError("redis 未安装，请执行: pip install redis")

    async def close_connection(self, conn: Any) -> None:
        """关闭 Redis 连接。"""
        if conn:
            await conn.aclose()

    async def execute_query(self, conn: Any, query: str, params: Any = None) -> Any:
        """
        执行 Redis 命令。

        查询格式为 JSON 字符串::

            {
                "operation": "benchmark",   # benchmark / info / slowlog / latency
                "command": "GET mykey",
                "iterations": 1000
            }

        对于 benchmark 操作，会重复执行指定命令并统计性能。

        Args:
            conn: Redis 客户端。
            query: 查询 JSON 字符串。
            params: 额外参数（未使用）。

        Returns:
            命令执行结果。
        """
        if isinstance(query, str):
            try:
                query_config = json.loads(query)
            except json.JSONDecodeError:
                # 非 JSON 格式，直接执行原始命令
                parts = query.strip().split()
                return await conn.execute_command(*parts)
        else:
            query_config = query

        operation = query_config.get("operation", "command")

        if operation == "command":
            # 执行单条命令
            command_str = query_config.get("command", "PING")
            parts = command_str.strip().split()
            return await conn.execute_command(*parts)

        elif operation == "benchmark":
            # 基准测试：重复执行命令
            command_str = query_config.get("command", "PING")
            iterations = query_config.get("iterations", 100)
            parts = command_str.strip().split()

            import time
            durations: List[float] = []
            errors = 0

            for _ in range(iterations):
                start = time.monotonic()
                try:
                    await conn.execute_command(*parts)
                except Exception:
                    errors += 1
                elapsed = (time.monotonic() - start) * 1000
                durations.append(elapsed)

            sorted_d = sorted(durations)
            return {
                "total": iterations,
                "errors": errors,
                "avg_ms": sum(durations) / len(durations) if durations else 0,
                "p50_ms": sorted_d[len(sorted_d) // 2] if sorted_d else 0,
                "p95_ms": sorted_d[int(len(sorted_d) * 0.95)] if sorted_d else 0,
                "p99_ms": sorted_d[int(len(sorted_d) * 0.99)] if sorted_d else 0,
            }

        elif operation == "info":
            return await conn.info()

        elif operation == "slowlog":
            count = query_config.get("count", 128)
            return await conn.slowlog_get(count)

        elif operation == "latency":
            # LATENCY HISTORY 或 LATENCY LATEST
            try:
                return await conn.execute_command("LATENCY", "LATEST")
            except Exception:
                return {}

        else:
            logger.warning(f"不支持的 Redis 操作: {operation}")
            return None
