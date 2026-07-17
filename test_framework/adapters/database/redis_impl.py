"""
基于 redis.asyncio 的 Redis 异步适配器。

特点：
- 纯异步 Redis 驱动
- 支持字符串/哈希/列表/集合/有序集合等数据结构
- 支持 Pipeline、Pub/Sub、慢查询分析
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .adapter import DatabaseAdapter, ExplainResult, QueryResult

logger = logging.getLogger(__name__)


class RedisAdapter(DatabaseAdapter):
    """
    Redis 异步适配器。

    配置项::

        {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "password": "",
            "decode_responses": True,
            "max_connections": 20,
            "socket_timeout": 5.0,
        }
    """

    @property
    def implementation_name(self) -> str:
        return "redis"

    def __init__(self) -> None:
        """初始化 Redis 适配器。"""
        self._client: Optional[Any] = None  # redis.asyncio.Redis

    async def connect(self, config: Dict[str, Any]) -> None:
        """
        创建 Redis 连接。

        Args:
            config: Redis 连接配置。
        """
        import redis.asyncio as aioredis

        self._client = aioredis.Redis(
            host=config.get("host", "localhost"),
            port=config.get("port", 6379),
            db=config.get("db", 0),
            password=config.get("password") or None,
            decode_responses=config.get("decode_responses", True),
            max_connections=config.get("max_connections", 20),
            socket_timeout=config.get("socket_timeout", 5.0),
        )
        # 验证连接
        await self._client.ping()
        logger.debug("RedisAdapter 已连接")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
        logger.debug("RedisAdapter 已断开")

    async def is_connected(self) -> bool:
        if not self._client:
            return False
        try:
            return await self._client.ping()
        except Exception:
            return False

    def _ensure_client(self) -> Any:
        """确保客户端可用。"""
        if not self._client:
            raise RuntimeError("RedisAdapter 未连接")
        return self._client

    # ===== 基本查询 =====

    async def execute(self, query: str, params: Any = None) -> QueryResult:
        """
        执行 Redis 命令。

        query 格式: "COMMAND arg1 arg2 ..."
        例如: "GET mykey" / "SET mykey myvalue" / "HGETALL myhash"

        Args:
            query: Redis 命令字符串。
            params: 忽略（Redis 命令直接解析）。

        Returns:
            查询结果。
        """
        client = self._ensure_client()
        parts = query.strip().split()
        if not parts:
            return QueryResult()

        command = parts[0].upper()
        args = parts[1:]

        start = time.monotonic()
        result = await client.execute_command(command, *args)
        elapsed = time.monotonic() - start

        # 统一转换为 QueryResult
        if isinstance(result, list):
            rows = [{"value": v} for v in result]
            return QueryResult(rows=rows, row_count=len(rows), duration=elapsed, raw=result)
        elif isinstance(result, dict):
            return QueryResult(rows=[result], row_count=1, duration=elapsed, raw=result)
        else:
            return QueryResult(
                rows=[{"value": result}],
                row_count=1 if result is not None else 0,
                duration=elapsed,
                raw=result,
            )

    async def execute_many(self, query: str, params_list: List[Any]) -> QueryResult:
        """使用 Pipeline 批量执行命令。"""
        client = self._ensure_client()
        start = time.monotonic()
        pipe = client.pipeline()
        for params in params_list:
            if isinstance(params, (list, tuple)):
                await pipe.execute_command(*params)
            elif isinstance(params, str):
                parts = params.strip().split()
                await pipe.execute_command(*parts)
        results = await pipe.execute()
        elapsed = time.monotonic() - start
        return QueryResult(
            rows=[{"value": r} for r in results],
            row_count=len(results),
            duration=elapsed,
            raw=results,
        )

    # ===== Redis 特有方法 =====

    async def get(self, key: str) -> QueryResult:
        """GET 命令。"""
        client = self._ensure_client()
        start = time.monotonic()
        value = await client.get(key)
        elapsed = time.monotonic() - start
        return QueryResult(
            rows=[{"key": key, "value": value}],
            row_count=1 if value is not None else 0,
            duration=elapsed,
        )

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> QueryResult:
        """SET 命令。"""
        client = self._ensure_client()
        start = time.monotonic()
        result = await client.set(key, value, ex=ex)
        elapsed = time.monotonic() - start
        return QueryResult(row_count=1, duration=elapsed, raw=result)

    async def delete(self, *keys: str) -> QueryResult:
        """DEL 命令。"""
        client = self._ensure_client()
        start = time.monotonic()
        count = await client.delete(*keys)
        elapsed = time.monotonic() - start
        return QueryResult(row_count=count, duration=elapsed)

    async def keys(self, pattern: str = "*") -> QueryResult:
        """KEYS 命令。"""
        client = self._ensure_client()
        start = time.monotonic()
        result = await client.keys(pattern)
        elapsed = time.monotonic() - start
        return QueryResult(
            rows=[{"key": k} for k in result],
            row_count=len(result),
            duration=elapsed,
        )

    async def slowlog_get(self, count: int = 20) -> QueryResult:
        """获取慢查询日志。"""
        client = self._ensure_client()
        start = time.monotonic()
        entries = await client.slowlog_get(count)
        elapsed = time.monotonic() - start
        rows = []
        for entry in entries:
            rows.append({
                "id": entry.get("id", 0),
                "duration_us": entry.get("duration", 0),
                "command": entry.get("command", ""),
                "timestamp": entry.get("start_time", 0),
            })
        return QueryResult(rows=rows, row_count=len(rows), duration=elapsed)

    async def info(self, section: str = "") -> QueryResult:
        """获取 Redis INFO 信息。"""
        client = self._ensure_client()
        start = time.monotonic()
        if section:
            result = await client.info(section)
        else:
            result = await client.info()
        elapsed = time.monotonic() - start
        return QueryResult(rows=[result], row_count=1, duration=elapsed, raw=result)

    # ===== 事务（Redis MULTI/EXEC） =====

    async def begin_transaction(self) -> None:
        """开始 Redis Pipeline 事务（MULTI）。"""
        client = self._ensure_client()
        self._pipeline = client.pipeline(transaction=True)

    async def commit(self) -> None:
        """提交 Pipeline 事务（EXEC）。"""
        if hasattr(self, "_pipeline") and self._pipeline:
            await self._pipeline.execute()
            self._pipeline = None

    async def rollback(self) -> None:
        """取消 Pipeline 事务（DISCARD）。"""
        if hasattr(self, "_pipeline") and self._pipeline:
            # Redis pipeline 没有显式 DISCARD，只需不执行
            self._pipeline = None

    # ===== 查询分析 =====

    async def explain(self, query: str, params: Any = None) -> ExplainResult:
        """Redis 无传统执行计划，使用 DEBUG OBJECT 或 LATENCY 信息替代。"""
        client = self._ensure_client()
        parts = query.strip().split()
        key = parts[1] if len(parts) > 1 else ""
        warnings: List[str] = []

        info_text = f"Command: {query}\n"
        if key:
            try:
                debug_info = await client.execute_command("DEBUG", "OBJECT", key)
                info_text += f"Debug Object: {debug_info}\n"
            except Exception:
                info_text += "DEBUG OBJECT not available\n"

        # 检查慢查询
        try:
            slowlog = await client.slowlog_get(5)
            if slowlog:
                info_text += f"Recent slowlog entries: {len(slowlog)}\n"
                for entry in slowlog[:3]:
                    warnings.append(
                        f"慢查询: {entry.get('command', '')} ({entry.get('duration', 0)}us)"
                    )
        except Exception:
            pass

        return ExplainResult(
            raw_text=info_text,
            warnings=warnings,
        )

    # ===== 元数据 =====

    async def get_tables(self) -> List[str]:
        """Redis 无表概念，返回所有 key 的模式（scan 采样）。"""
        client = self._ensure_client()
        keys = await client.keys("*")
        # 提取 key 前缀作为"表"
        prefixes = set()
        for key in keys[:1000]:  # 限制采样
            k = str(key)
            if ":" in k:
                prefixes.add(k.split(":")[0])
            else:
                prefixes.add(k)
        return sorted(prefixes)

    async def get_columns(self, table: str) -> List[Dict[str, Any]]:
        """Redis 无列概念，返回 key 的类型信息。"""
        client = self._ensure_client()
        keys = await client.keys(f"{table}:*")
        type_info: Dict[str, str] = {}
        for key in keys[:100]:
            key_type = await client.type(key)
            type_info[str(key)] = key_type
        return [{"name": k, "type": v, "nullable": True, "default": None} for k, v in type_info.items()]

    async def get_indexes(self, table: str) -> List[Dict[str, Any]]:
        """Redis 无索引概念。"""
        return []
