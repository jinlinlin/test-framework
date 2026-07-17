"""
MySQL 方言 — 基于 aiomysql 实现。

职责：处理 MySQL 特有的 SQL 语法、连接管理、执行计划解析。
依赖：aiomysql（延迟导入）
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .base import Dialect

logger = logging.getLogger(__name__)


class MySQLDialect(Dialect):
    """
    MySQL 方言实现。

    使用 aiomysql 驱动，支持 EXPLAIN FORMAT=JSON 进行执行计划分析。

    Attributes:
        _pool: aiomysql 连接池。
    """

    @property
    def name(self) -> str:
        """方言名称。"""
        return "mysql"

    def build_explain_query(self, sql: str) -> str:
        """
        构建 MySQL EXPLAIN 查询。

        Args:
            sql: 原始 SQL 查询。

        Returns:
            EXPLAIN 查询语句。
        """
        return f"EXPLAIN FORMAT=JSON {sql}"

    def parse_explain_result(self, result: Any) -> Dict[str, Any]:
        """
        解析 MySQL EXPLAIN JSON 输出。

        Args:
            result: EXPLAIN 返回的结果。

        Returns:
            统一格式的执行计划字典。
        """
        try:
            # aiomysql 返回元组列表
            if isinstance(result, (list, tuple)) and len(result) > 0:
                raw = result[0]
                if isinstance(raw, (tuple, list)):
                    raw_str = str(raw[0]) if raw else "{}"
                else:
                    raw_str = str(raw)
                plan_data = json.loads(raw_str)
            elif isinstance(result, str):
                plan_data = json.loads(result)
            else:
                plan_data = result if isinstance(result, dict) else {}

            return self._extract_plan(plan_data)

        except Exception as e:
            logger.warning(f"MySQL EXPLAIN 结果解析失败: {e}")
            return {
                "plan_type": "unknown",
                "estimated_cost": 0,
                "estimated_rows": 0,
                "actual_rows": 0,
                "tables": [],
                "indexes_used": [],
                "warnings": [f"解析失败: {e}"],
            }

    def get_connection_string(self, config: Dict[str, Any]) -> str:
        """
        生成 MySQL 连接配置字符串。

        Args:
            config: 连接配置字典。

        Returns:
            MySQL 连接字符串。
        """
        host = config.get("host", "localhost")
        port = config.get("port", 3306)
        database = config.get("database", "")
        user = config.get("user", "root")
        password = config.get("password", "")

        return f"mysql://{user}:{password}@{host}:{port}/{database}"

    async def create_connection(self, conn_str: str) -> Any:
        """
        创建 aiomysql 连接。

        Args:
            conn_str: MySQL 连接字符串（仅用于日志，实际解析 config）。

        Returns:
            aiomysql Connection 对象。
        """
        try:
            import aiomysql
            # 从连接字符串解析参数
            parts = conn_str.replace("mysql://", "").split("@")
            user_pass = parts[0].split(":")
            host_db = parts[1].split("/") if len(parts) > 1 else ["localhost:3306", ""]
            host_port = host_db[0].split(":")

            conn = await aiomysql.connect(
                host=host_port[0],
                port=int(host_port[1]) if len(host_port) > 1 else 3306,
                user=user_pass[0],
                password=user_pass[1] if len(user_pass) > 1 else "",
                db=host_db[1] if len(host_db) > 1 else "",
            )
            logger.debug(f"MySQL 连接已创建")
            return conn
        except ImportError:
            raise ImportError("aiomysql 未安装，请执行: pip install aiomysql")

    async def close_connection(self, conn: Any) -> None:
        """关闭 aiomysql 连接。"""
        if conn:
            conn.close()

    async def execute_query(self, conn: Any, query: str, params: Any = None) -> Any:
        """
        执行 MySQL 查询。

        Args:
            conn: aiomysql Connection。
            query: SQL 查询。
            params: 查询参数。

        Returns:
            查询结果列表。
        """
        async with conn.cursor() as cur:
            if params:
                await cur.execute(query, params)
            else:
                await cur.execute(query)
            return await cur.fetchall()

    # ===== 私有方法 =====

    def _extract_plan(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从 MySQL EXPLAIN JSON 中提取关键信息。

        Args:
            plan_data: EXPLAIN JSON 数据。

        Returns:
            统一格式的执行计划字典。
        """
        result = {
            "plan_type": "unknown",
            "estimated_cost": 0.0,
            "estimated_rows": 0,
            "actual_rows": 0,
            "tables": [],
            "indexes_used": [],
            "warnings": [],
            "raw_plan": plan_data,
        }

        # MySQL EXPLAIN JSON 结构
        query_block = plan_data.get("query_block", {})
        ordering_op = query_block.get("ordering_operation", {})
        table_info = (
            ordering_op.get("table", {})
            or query_block.get("table", {})
            or query_block.get("nested_loop", [{}])[0].get("table", {})
            if query_block.get("nested_loop")
            else {}
        )

        if table_info:
            result["plan_type"] = table_info.get("access_type", "unknown")
            result["estimated_rows"] = table_info.get("rows_examined_per_scan", 0)
            result["estimated_cost"] = table_info.get("cost_info", {}).get("query_cost", 0)
            result["tables"].append(table_info.get("table_name", ""))

            # 索引信息
            used_key = table_info.get("key", "")
            if used_key:
                result["indexes_used"].append(used_key)

            # 全表扫描检测
            if table_info.get("access_type") == "ALL":
                result["warnings"].append(
                    f"检测到全表扫描: 表 '{table_info.get('table_name', '')}'"
                )

        return result
