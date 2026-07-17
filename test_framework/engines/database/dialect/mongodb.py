"""
MongoDB 方言 — 基于 motor 实现。

职责：处理 MongoDB 特有的查询语法、连接管理、执行计划解析。
依赖：motor（延迟导入）
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .base import Dialect

logger = logging.getLogger(__name__)


class MongoDBDialect(Dialect):
    """
    MongoDB 方言实现。

    使用 motor 异步驱动，通过 explain() 方法进行执行计划分析。
    MongoDB 不使用 SQL，查询语句以 JSON 格式传递。

    Attributes:
        _client: motor 异步客户端。
    """

    @property
    def name(self) -> str:
        """方言名称。"""
        return "mongodb"

    def build_explain_query(self, sql: str) -> str:
        """
        MongoDB 不直接使用 EXPLAIN SQL，此方法返回原始查询。

        实际执行计划分析在 execute_query 中通过 explain() 方法完成。

        Args:
            sql: 查询 JSON 字符串（如 '{"collection":"users","filter":{"age":{"$gt":18}}}'）。

        Returns:
            原始查询字符串。
        """
        return sql  # MongoDB 使用 collection.find().explain()

    def parse_explain_result(self, result: Any) -> Dict[str, Any]:
        """
        解析 MongoDB explain() 输出。

        Args:
            result: MongoDB explain() 返回的字典。

        Returns:
            统一格式的执行计划字典。
        """
        try:
            if isinstance(result, str):
                result = json.loads(result)

            query_planner = result.get("queryPlanner", {})
            execution_stats = result.get("executionStats", {})
            winning_plan = query_planner.get("winningPlan", {})

            plan_type = self._extract_plan_type(winning_plan)
            tables = self._extract_collections(winning_plan)
            indexes = self._extract_indexes(winning_plan)

            # 执行统计
            n_returned = execution_stats.get("nReturned", 0)
            total_docs = execution_stats.get("totalDocsExamined", 0)
            total_keys = execution_stats.get("totalKeysExamined", 0)
            exec_time = execution_stats.get("executionTimeMillis", 0)

            warnings: List[str] = []
            # COLLSCAN 表示全集合扫描
            if "COLLSCAN" in plan_type:
                warnings.append("检测到全集合扫描（COLLSCAN），建议添加索引")
            # 扫描文档数远大于返回数
            if total_docs > 0 and n_returned > 0 and total_docs / n_returned > 10:
                warnings.append(
                    f"扫描效率低: 扫描 {total_docs} 文档，返回 {n_returned} 条"
                )

            return {
                "plan_type": plan_type,
                "estimated_cost": exec_time,
                "estimated_rows": total_docs,
                "actual_rows": n_returned,
                "tables": tables,
                "indexes_used": indexes,
                "warnings": warnings,
                "execution_time_ms": exec_time,
                "docs_examined": total_docs,
                "keys_examined": total_keys,
            }

        except Exception as e:
            logger.warning(f"MongoDB explain 结果解析失败: {e}")
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
        生成 MongoDB 连接字符串。

        Args:
            config: 连接配置字典。

        Returns:
            MongoDB URI。
        """
        host = config.get("host", "localhost")
        port = config.get("port", 27017)
        database = config.get("database", "test")
        user = config.get("user", "")
        password = config.get("password", "")

        if user and password:
            return f"mongodb://{user}:{password}@{host}:{port}/{database}"
        return f"mongodb://{host}:{port}/{database}"

    async def create_connection(self, conn_str: str) -> Any:
        """
        创建 motor 异步连接。

        Args:
            conn_str: MongoDB URI。

        Returns:
            motor 数据库对象。
        """
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(conn_str)
            # 从 URI 提取数据库名
            db_name = conn_str.rsplit("/", 1)[-1].split("?")[0] or "test"
            db = client[db_name]
            logger.debug(f"MongoDB 连接已创建: {db_name}")
            return {"client": client, "db": db}
        except ImportError:
            raise ImportError("motor 未安装，请执行: pip install motor")

    async def close_connection(self, conn: Any) -> None:
        """关闭 motor 连接。"""
        if conn and isinstance(conn, dict):
            client = conn.get("client")
            if client:
                client.close()

    async def execute_query(self, conn: Any, query: str, params: Any = None) -> Any:
        """
        执行 MongoDB 查询。

        查询格式为 JSON 字符串::

            {
                "collection": "users",
                "operation": "find",        # find / aggregate / count
                "filter": {"age": {"$gt": 18}},
                "projection": {"name": 1},
                "sort": {"age": -1},
                "limit": 10
            }

        Args:
            conn: motor 连接字典（含 client 和 db）。
            query: 查询 JSON 字符串。
            params: 额外参数（未使用）。

        Returns:
            查询结果列表。
        """
        if isinstance(query, str):
            query_config = json.loads(query)
        else:
            query_config = query

        db = conn["db"]
        collection_name = query_config.get("collection", "")
        operation = query_config.get("operation", "find")
        filter_query = query_config.get("filter", {})
        projection = query_config.get("projection", {})
        sort_query = query_config.get("sort", {})
        limit = query_config.get("limit", 0)

        collection = db[collection_name]

        if operation == "find":
            cursor = collection.find(filter_query, projection)
            if sort_query:
                cursor = cursor.sort(list(sort_query.items()))
            if limit:
                cursor = cursor.limit(limit)
            return await cursor.to_list(length=limit or 1000)

        elif operation == "count":
            return await collection.count_documents(filter_query)

        elif operation == "aggregate":
            pipeline = query_config.get("pipeline", [])
            cursor = collection.aggregate(pipeline)
            return await cursor.to_list(length=1000)

        else:
            logger.warning(f"不支持的 MongoDB 操作: {operation}")
            return []

    # ===== 私有方法 =====

    def _extract_plan_type(self, plan: Dict[str, Any]) -> str:
        """从执行计划节点中提取计划类型。"""
        stage = plan.get("stage", "")
        input_stage = plan.get("inputStage", {})
        if input_stage:
            inner = self._extract_plan_type(input_stage)
            return f"{stage} -> {inner}" if inner else stage
        return stage

    def _extract_collections(self, plan: Dict[str, Any]) -> List[str]:
        """递归收集涉及的集合名。"""
        collections = []
        if "collectionName" in plan:
            collections.append(plan["collectionName"])
        if "inputStage" in plan:
            collections.extend(self._extract_collections(plan["inputStage"]))
        if "inputStages" in plan:
            for stage in plan["inputStages"]:
                collections.extend(self._extract_collections(stage))
        return collections

    def _extract_indexes(self, plan: Dict[str, Any]) -> List[str]:
        """递归收集使用的索引名。"""
        indexes = []
        if "indexName" in plan:
            indexes.append(plan["indexName"])
        if "inputStage" in plan:
            indexes.extend(self._extract_indexes(plan["inputStage"]))
        if "inputStages" in plan:
            for stage in plan["inputStages"]:
                indexes.extend(self._extract_indexes(stage))
        return indexes
