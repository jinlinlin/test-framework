"""
基于 aiomysql 的 MySQL 异步适配器。

特点：
- 纯异步 MySQL 驱动
- 支持连接池、事务、参数化查询
- 兼容 MySQL 5.7+ / 8.0+
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .adapter import DatabaseAdapter, ExplainResult, QueryResult

logger = logging.getLogger(__name__)


class AiomysqlAdapter(DatabaseAdapter):
    """
    aiomysql MySQL 异步适配器。

    配置项::

        {
            "host": "localhost",
            "port": 3306,
            "db": "test_db",
            "user": "root",
            "password": "",
            "minsize": 2,
            "maxsize": 10,
            "charset": "utf8mb4",
            "autocommit": True,
        }
    """

    @property
    def implementation_name(self) -> str:
        return "aiomysql"

    def __init__(self) -> None:
        """初始化 aiomysql 适配器。"""
        self._pool: Optional[Any] = None
        self._connection: Optional[Any] = None
        self._transaction_conn: Optional[Any] = None

    async def connect(self, config: Dict[str, Any]) -> None:
        """
        创建连接池。

        Args:
            config: MySQL 连接配置。
        """
        import aiomysql

        use_pool = config.get("use_pool", True)
        conn_kwargs = {
            "host": config.get("host", "localhost"),
            "port": config.get("port", 3306),
            "db": config.get("database", "test_db"),
            "user": config.get("user", "root"),
            "password": config.get("password", ""),
            "charset": config.get("charset", "utf8mb4"),
            "autocommit": config.get("autocommit", True),
        }

        if use_pool:
            self._pool = await aiomysql.create_pool(
                minsize=config.get("min_size", 2),
                maxsize=config.get("max_size", 10),
                **conn_kwargs,
            )
            logger.debug("AiomysqlAdapter 连接池已创建")
        else:
            self._connection = await aiomysql.connect(**conn_kwargs)
            logger.debug("AiomysqlAdapter 单连接已创建")

    async def disconnect(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
        if self._connection:
            self._connection.close()
            self._connection = None
        logger.debug("AiomysqlAdapter 已断开")

    async def is_connected(self) -> bool:
        if self._pool:
            return not self._pool.closed
        if self._connection:
            return self._connection.open
        return False

    async def _get_connection(self) -> Any:
        """获取连接。"""
        if self._pool:
            return await self._pool.acquire()
        if self._connection:
            return self._connection
        raise RuntimeError("AiomysqlAdapter 未连接")

    async def _release_connection(self, conn: Any) -> None:
        if self._pool and conn:
            self._pool.release(conn)

    # ===== 基本查询 =====

    async def execute(self, query: str, params: Any = None) -> QueryResult:
        conn = await self._get_connection()
        try:
            start = time.monotonic()
            async with conn.cursor() as cur:
                # MySQL 参数化使用 %s 占位符
                if params:
                    await cur.execute(query, params)
                else:
                    await cur.execute(query)

                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows_raw = await cur.fetchall()
                    # 转换为字典列表
                    rows = [dict(zip(columns, row)) for row in rows_raw]
                else:
                    columns = []
                    rows = []

                elapsed = time.monotonic() - start
                return QueryResult(
                    rows=rows,
                    columns=columns,
                    row_count=cur.rowcount,
                    duration=elapsed,
                )
        finally:
            if self._pool:
                self._release_connection(conn)

    async def execute_many(self, query: str, params_list: List[Any]) -> QueryResult:
        conn = await self._get_connection()
        try:
            start = time.monotonic()
            async with conn.cursor() as cur:
                await cur.executemany(query, params_list)
                elapsed = time.monotonic() - start
                return QueryResult(
                    row_count=cur.rowcount,
                    duration=elapsed,
                )
        finally:
            if self._pool:
                self._release_connection(conn)

    # ===== 事务 =====

    async def begin_transaction(self) -> None:
        conn = await self._get_connection()
        self._transaction_conn = conn
        await conn.begin()

    async def commit(self) -> None:
        if self._transaction_conn:
            await self._transaction_conn.commit()
            if self._pool:
                self._release_connection(self._transaction_conn)
            self._transaction_conn = None

    async def rollback(self) -> None:
        if self._transaction_conn:
            await self._transaction_conn.rollback()
            if self._pool:
                self._release_connection(self._transaction_conn)
            self._transaction_conn = None

    # ===== 查询分析 =====

    async def explain(self, query: str, params: Any = None) -> ExplainResult:
        """获取 MySQL 执行计划（EXPLAIN FORMAT=JSON）。"""
        import json

        explain_query = f"EXPLAIN FORMAT=JSON {query}"
        result = await self.execute(explain_query, params)

        warnings: List[str] = []
        total_cost = 0.0
        estimated_rows = 0.0
        raw_text = ""

        if result.rows:
            raw_json_str = result.rows[0].get("EXPLAIN", "")
            try:
                plan_data = json.loads(raw_json_str)
                raw_text = json.dumps(plan_data, indent=2, ensure_ascii=False)
                query_block = plan_data.get("query_block", {})
                ordering_op = query_block.get("ordering_operation", query_block)
                table_info = ordering_op.get("table", {})

                if isinstance(table_info, dict):
                    estimated_rows = table_info.get("rows_examined_per_scan", 0)
                    total_cost = table_info.get("cost_info", {}).get("query_cost", 0)
                    # 检测全表扫描
                    access_type = table_info.get("access_type", "")
                    if access_type == "ALL":
                        warnings.append(
                            f"检测到全表扫描: {table_info.get('table_name', 'unknown')}"
                        )
            except (json.JSONDecodeError, TypeError):
                raw_text = raw_json_str

        return ExplainResult(
            plan=result.rows[0] if result.rows else None,
            raw_text=raw_text,
            total_cost=float(total_cost),
            estimated_rows=float(estimated_rows),
            warnings=warnings,
        )

    # ===== 元数据 =====

    async def get_tables(self) -> List[str]:
        result = await self.execute("SHOW TABLES")
        if not result.rows:
            return []
        # SHOW TABLES 返回的第一个列名是动态的
        key = result.columns[0]
        return [row[key] for row in result.rows]

    async def get_columns(self, table: str) -> List[Dict[str, Any]]:
        result = await self.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (table,),
        )
        return [
            {
                "name": row["COLUMN_NAME"],
                "type": row["DATA_TYPE"],
                "nullable": row["IS_NULLABLE"] == "YES",
                "default": row["COLUMN_DEFAULT"],
                "key": row["COLUMN_KEY"],
            }
            for row in result.rows
        ]

    async def get_indexes(self, table: str) -> List[Dict[str, Any]]:
        result = await self.execute(f"SHOW INDEX FROM {table}")
        indexes: Dict[str, Dict[str, Any]] = {}
        for row in result.rows:
            name = row.get("Key_name", "")
            if name not in indexes:
                indexes[name] = {
                    "name": name,
                    "unique": not row.get("Non_unique", True),
                    "columns": [],
                }
            indexes[name]["columns"].append(row.get("Column_name", ""))
        return list(indexes.values())
