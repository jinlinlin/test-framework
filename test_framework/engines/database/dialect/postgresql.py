"""
PostgreSQL 方言 — 基于 asyncpg 实现。

职责：处理 PostgreSQL 特有的 SQL 语法、连接管理、执行计划解析。
依赖：asyncpg（延迟导入）
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .base import Dialect

logger = logging.getLogger(__name__)


class PostgreSQLDialect(Dialect):
    """
    PostgreSQL 方言实现。

    使用 asyncpg 驱动，支持 EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
    进行执行计划分析。

    Attributes:
        _conn: asyncpg 连接对象。
    """

    @property
    def name(self) -> str:
        """方言名称。"""
        return "postgresql"

    def build_explain_query(self, sql: str) -> str:
        """
        构建 PostgreSQL EXPLAIN 查询。

        使用 ANALYZE + BUFFERS + JSON 格式输出。

        Args:
            sql: 原始 SQL 查询。

        Returns:
            EXPLAIN 查询语句。
        """
        return f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {sql}"

    def parse_explain_result(self, result: Any) -> Dict[str, Any]:
        """
        解析 PostgreSQL EXPLAIN JSON 输出。

        Args:
            result: EXPLAIN 返回的结果（可能是 JSON 字符串或列表）。

        Returns:
            统一格式的执行计划字典。
        """
        try:
            # asyncpg 返回 Record 列表，EXPLAIN JSON 格式返回文本
            if isinstance(result, list) and len(result) > 0:
                raw = result[0]
                # 可能是字符串或字典
                if isinstance(raw, str):
                    plan_data = json.loads(raw)
                elif isinstance(raw, dict):
                    plan_data = raw
                else:
                    # asyncpg Record 对象
                    plan_data = json.loads(str(raw))
            elif isinstance(result, str):
                plan_data = json.loads(result)
            else:
                plan_data = result if isinstance(result, (dict, list)) else {}

            # 提取关键信息
            plan = self._extract_plan(plan_data)
            return plan

        except Exception as e:
            logger.warning(f"PostgreSQL EXPLAIN 结果解析失败: {e}")
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
        生成 PostgreSQL 连接字符串。

        Args:
            config: 连接配置字典。
                - host: 主机地址
                - port: 端口（默认 5432）
                - database: 数据库名
                - user: 用户名
                - password: 密码

        Returns:
            PostgreSQL 连接字符串。
        """
        host = config.get("host", "localhost")
        port = config.get("port", 5432)
        database = config.get("database", "postgres")
        user = config.get("user", "postgres")
        password = config.get("password", "")

        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    async def create_connection(self, conn_str: str) -> Any:
        """
        创建 asyncpg 连接。

        Args:
            conn_str: PostgreSQL 连接字符串。

        Returns:
            asyncpg Connection 对象。
        """
        try:
            import asyncpg
            conn = await asyncpg.connect(conn_str)
            logger.debug(f"PostgreSQL 连接已创建: {conn_str.split('@')[-1] if '@' in conn_str else conn_str}")
            return conn
        except ImportError:
            raise ImportError("asyncpg 未安装，请执行: pip install asyncpg")

    async def close_connection(self, conn: Any) -> None:
        """
        关闭 asyncpg 连接。

        Args:
            conn: asyncpg Connection 对象。
        """
        if conn:
            await conn.close()

    async def execute_query(self, conn: Any, query: str, params: Any = None) -> Any:
        """
        执行 PostgreSQL 查询。

        Args:
            conn: asyncpg Connection。
            query: SQL 查询。
            params: 查询参数（元组）。

        Returns:
            查询结果列表。
        """
        if params:
            return await conn.fetch(query, *params)
        return await conn.fetch(query)

    # ===== 私有方法 =====

    def _extract_plan(self, plan_data: Any) -> Dict[str, Any]:
        """
        从 EXPLAIN JSON 中提取关键执行计划信息。

        Args:
            plan_data: EXPLAIN 输出的 JSON 数据。

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

        # 处理顶层数组（PostgreSQL EXPLAIN 返回数组）
        if isinstance(plan_data, list) and len(plan_data) > 0:
            plan_node = plan_data[0].get("Plan", plan_data[0])
        elif isinstance(plan_data, dict):
            plan_node = plan_data.get("Plan", plan_data)
        else:
            return result

        # 提取节点类型
        result["plan_type"] = plan_node.get("Node Type", "unknown")

        # 提取代价和行数
        result["estimated_cost"] = plan_node.get("Total Cost", 0)
        result["estimated_rows"] = plan_node.get("Plan Rows", 0)
        result["actual_rows"] = plan_node.get("Actual Rows", 0)

        # 递归收集表和索引
        tables, indexes = self._collect_tables_indexes(plan_node)
        result["tables"] = list(set(tables))
        result["indexes_used"] = list(set(indexes))

        # 检测全表扫描
        if plan_node.get("Node Type") == "Seq Scan":
            table_name = plan_node.get("Relation Name", "")
            result["warnings"].append(
                f"检测到全表扫描: 表 '{table_name}'，建议添加索引"
            )

        # 检测高代价操作
        if result["estimated_cost"] > 10000:
            result["warnings"].append(
                f"预估代价较高: {result['estimated_cost']}"
            )

        return result

    def _collect_tables_indexes(self, node: Dict[str, Any]) -> tuple:
        """
        递归收集执行计划中的表名和索引名。

        Args:
            node: 执行计划节点。

        Returns:
            (tables, indexes) 元组。
        """
        tables: List[str] = []
        indexes: List[str] = []

        # 当前节点
        if "Relation Name" in node:
            tables.append(node["Relation Name"])
        if "Index Name" in node:
            indexes.append(node["Index Name"])

        # 递归子节点
        for child in node.get("Plans", []):
            child_tables, child_indexes = self._collect_tables_indexes(child)
            tables.extend(child_tables)
            indexes.extend(child_indexes)

        return tables, indexes
