"""
基于 asyncpg 的 PostgreSQL 异步适配器。

特点：
- 纯异步高性能 PostgreSQL 驱动
- 支持连接池、事务、prepared statements
- 自动类型转换
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .adapter import DatabaseAdapter, ExplainResult, QueryResult

logger = logging.getLogger(__name__)


class AsyncpgAdapter(DatabaseAdapter):
    """
    asyncpg PostgreSQL 异步适配器。

    配置项::

        {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "postgres",
            "password": "postgres",
            "min_size": 2,
            "max_size": 10,
            "ssl": False,
            "statement_cache_size": 100,
        }
    """

    @property
    def implementation_name(self) -> str:
        return "asyncpg"

    def __init__(self) -> None:
        """初始化 asyncpg 适配器。"""
        self._pool: Optional[Any] = None  # asyncpg.Pool 实例
        self._connection: Optional[Any] = None  # 单连接模式

    async def connect(self, config: Dict[str, Any]) -> None:
        """
        创建连接池。

        Args:
            config: PostgreSQL 连接配置。
        """
        import asyncpg

        use_pool = config.get("use_pool", True)
        conn_kwargs = {
            "host": config.get("host", "localhost"),
            "port": config.get("port", 5432),
            "database": config.get("database", "test_db"),
            "user": config.get("user", "postgres"),
            "password": config.get("password", ""),
            "ssl": config.get("ssl", False),
        }

        if use_pool:
            self._pool = await asyncpg.create_pool(
                min_size=config.get("min_size", 2),
                max_size=config.get("max_size", 10),
                statement_cache_size=config.get("statement_cache_size", 100),
                **conn_kwargs,
            )
            logger.debug("AsyncpgAdapter 连接池已创建")
        else:
            self._connection = await asyncpg.connect(**conn_kwargs)
            logger.debug("AsyncpgAdapter 单连接已创建")

    async def disconnect(self) -> None:
        """关闭连接池或单连接。"""
        if self._pool:
            await self._pool.close()
            self._pool = None
        if self._connection:
            await self._connection.close()
            self._connection = None
        logger.debug("AsyncpgAdapter 已断开")

    async def is_connected(self) -> bool:
        if self._pool:
            return True
        if self._connection:
            return not self._connection.is_closed()
        return False

    async def _get_connection(self) -> Any:
        """获取数据库连接（从连接池或单连接）。"""
        if self._pool:
            return await self._pool.acquire()
        if self._connection:
            return self._connection
        raise RuntimeError("AsyncpgAdapter 未连接")

    async def _release_connection(self, conn: Any) -> None:
        """释放连接到池。"""
        if self._pool and conn:
            await self._pool.release(conn)

    # ===== 基本查询 =====

    async def execute(self, query: str, params: Any = None) -> QueryResult:
        conn = await self._get_connection()
        try:
            start = time.monotonic()
            if params:
                result = await conn.fetch(query, *params)
            else:
                result = await conn.fetch(query)
            elapsed = time.monotonic() - start

            rows = [dict(row) for row in result]
            columns = list(rows[0].keys()) if rows else []
            return QueryResult(
                rows=rows,
                columns=columns,
                row_count=len(rows),
                duration=elapsed,
                raw=result,
            )
        finally:
            if self._pool:
                await self._release_connection(conn)

    async def execute_many(self, query: str, params_list: List[Any]) -> QueryResult:
        conn = await self._get_connection()
        try:
            start = time.monotonic()
            await conn.executemany(query, params_list)
            elapsed = time.monotonic() - start
            return QueryResult(
                row_count=len(params_list),
                duration=elapsed,
            )
        finally:
            if self._pool:
                await self._release_connection(conn)

    # ===== 事务 =====

    async def begin_transaction(self) -> None:
        """开始事务（获取连接后需要手动管理）。"""
        conn = await self._get_connection()
        self._transaction_conn = conn
        self._transaction = conn.transaction()
        await self._transaction.start()

    async def commit(self) -> None:
        if hasattr(self, "_transaction") and self._transaction:
            await self._transaction.commit()
            if hasattr(self, "_transaction_conn"):
                await self._release_connection(self._transaction_conn)
            self._transaction = None

    async def rollback(self) -> None:
        if hasattr(self, "_transaction") and self._transaction:
            await self._transaction.rollback()
            if hasattr(self, "_transaction_conn"):
                await self._release_connection(self._transaction_conn)
            self._transaction = None

    # ===== 查询分析 =====

    async def explain(self, query: str, params: Any = None) -> ExplainResult:
        """获取 PostgreSQL 执行计划（EXPLAIN ANALYZE BUFFERS FORMAT JSON）。"""
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
        result = await self.execute(explain_query, params)

        import json
        warnings: List[str] = []
        total_cost = 0.0
        estimated_rows = 0.0
        raw_text = ""

        if result.rows:
            plan_data = result.rows[0]
            # asyncpg 返回 JSON 格式的 QUERY PLAN
            if isinstance(plan_data, dict):
                raw_text = json.dumps(plan_data, indent=2, ensure_ascii=False)
                plan_node = plan_data.get("Plan", {})
            else:
                raw_text = str(plan_data)
                plan_node = {}

            total_cost = plan_node.get("Total Cost", 0.0)
            estimated_rows = plan_node.get("Plan Rows", 0.0)

            # 检测全表扫描
            if plan_node.get("Node Type") == "Seq Scan":
                warnings.append(f"检测到全表扫描: {plan_node.get('Relation Name', 'unknown')}")
            # 检测高代价
            if total_cost > 1000:
                warnings.append(f"执行计划代价较高: {total_cost}")

        return ExplainResult(
            plan=result.rows[0] if result.rows else None,
            raw_text=raw_text,
            total_cost=total_cost,
            estimated_rows=estimated_rows,
            warnings=warnings,
        )

    # ===== 元数据 =====

    async def get_tables(self) -> List[str]:
        result = await self.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        return [row["tablename"] for row in result.rows]

    async def get_columns(self, table: str) -> List[Dict[str, Any]]:
        result = await self.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position
            """,
            [table],
        )
        return [
            {
                "name": row["column_name"],
                "type": row["data_type"],
                "nullable": row["is_nullable"] == "YES",
                "default": row["column_default"],
            }
            for row in result.rows
        ]

    async def get_indexes(self, table: str) -> List[Dict[str, Any]]:
        result = await self.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = $1
            ORDER BY indexname
            """,
            [table],
        )
        return [
            {"name": row["indexname"], "definition": row["indexdef"]}
            for row in result.rows
        ]
