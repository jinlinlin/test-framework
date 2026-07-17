"""
基于 motor 的 MongoDB 异步适配器。

特点：
- 纯异步 MongoDB 驱动（motor 是 pymongo 的异步封装）
- 支持 CRUD、聚合管道、索引管理
- BSON 文档自动转换
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from .adapter import DatabaseAdapter, ExplainResult, QueryResult

logger = logging.getLogger(__name__)


class MotorAdapter(DatabaseAdapter):
    """
    motor MongoDB 异步适配器。

    配置项::

        {
            "uri": "mongodb://localhost:27017",
            "database": "test_db",
            "max_pool_size": 10,
            "min_pool_size": 2,
            "server_selection_timeout_ms": 5000,
        }
    """

    @property
    def implementation_name(self) -> str:
        return "motor"

    def __init__(self) -> None:
        """初始化 motor 适配器。"""
        self._client: Optional[Any] = None  # MotorClient
        self._db: Optional[Any] = None  # MotorDatabase

    async def connect(self, config: Dict[str, Any]) -> None:
        """
        创建 MongoDB 连接。

        Args:
            config: MongoDB 连接配置。
        """
        from motor.motor_asyncio import AsyncIOMotorClient

        uri = config.get("uri", "mongodb://localhost:27017")
        database = config.get("database", "test_db")
        max_pool_size = config.get("max_pool_size", 10)
        min_pool_size = config.get("min_pool_size", 2)
        timeout = config.get("server_selection_timeout_ms", 5000)

        self._client = AsyncIOMotorClient(
            uri,
            maxPoolSize=max_pool_size,
            minPoolSize=min_pool_size,
            serverSelectionTimeoutMS=timeout,
        )
        self._db = self._client[database]

        # 验证连接
        await self._client.admin.command("ping")
        logger.debug(f"MotorAdapter 已连接: database={database}")

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
        logger.debug("MotorAdapter 已断开")

    async def is_connected(self) -> bool:
        if not self._client:
            return False
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            return False

    def _ensure_db(self) -> Any:
        """确保数据库可用。"""
        if not self._db:
            raise RuntimeError("MotorAdapter 未连接")
        return self._db

    def _collection(self, table: str) -> Any:
        """获取集合（collection）引用。"""
        return self._ensure_db()[table]

    # ===== 基本查询 =====

    async def execute(self, query: str, params: Any = None) -> QueryResult:
        """
        执行 MongoDB 命令（通过 JSON 格式的命令字符串）。

        对于 MongoDB，query 被解析为 JSON 命令。
        推荐使用具体的 find/insert 等方法而非 execute。

        Args:
            query: JSON 格式的命令字符串或集合操作名。
            params: 命令参数。

        Returns:
            查询结果。
        """
        import json

        db = self._ensure_db()
        start = time.monotonic()

        try:
            # 尝试解析为 JSON 命令
            cmd = json.loads(query)
            result = await db.command(cmd)
            elapsed = time.monotonic() - start
            return QueryResult(
                rows=[result],
                duration=elapsed,
                raw=result,
            )
        except (json.JSONDecodeError, TypeError):
            # 作为普通命令名执行
            result = await db.command(query)
            elapsed = time.monotonic() - start
            return QueryResult(
                rows=[result],
                duration=elapsed,
                raw=result,
            )

    async def execute_many(self, query: str, params_list: List[Any]) -> QueryResult:
        """批量插入文档。"""
        # MongoDB 场景下，query 作为集合名使用
        db = self._ensure_db()
        collection = db[query]
        start = time.monotonic()
        result = await collection.insert_many(params_list)
        elapsed = time.monotonic() - start
        return QueryResult(
            row_count=len(result.inserted_ids),
            duration=elapsed,
            raw=result,
        )

    # ===== MongoDB 特有方法 =====

    async def find(
        self,
        collection: str,
        filter: Optional[Dict[str, Any]] = None,
        projection: Optional[Dict[str, Any]] = None,
        sort: Optional[List] = None,
        limit: int = 100,
    ) -> QueryResult:
        """
        查询文档。

        Args:
            collection: 集合名。
            filter: 查询过滤器。
            projection: 字段投影。
            sort: 排序规则 [(field, direction), ...]。
            limit: 返回数量限制。

        Returns:
            查询结果。
        """
        coll = self._collection(collection)
        start = time.monotonic()
        cursor = coll.find(filter or {}, projection)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.limit(limit)

        docs = await cursor.to_list(length=limit)
        elapsed = time.monotonic() - start
        # 将 ObjectId 转为字符串
        rows = []
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            rows.append(doc)

        return QueryResult(
            rows=rows,
            columns=list(rows[0].keys()) if rows else [],
            row_count=len(rows),
            duration=elapsed,
        )

    async def insert_one(self, collection: str, document: Dict[str, Any]) -> QueryResult:
        """插入单个文档。"""
        coll = self._collection(collection)
        start = time.monotonic()
        result = await coll.insert_one(document)
        elapsed = time.monotonic() - start
        return QueryResult(
            rows=[{"_id": str(result.inserted_id)}],
            row_count=1,
            duration=elapsed,
        )

    async def update_many(
        self,
        collection: str,
        filter: Dict[str, Any],
        update: Dict[str, Any],
    ) -> QueryResult:
        """批量更新文档。"""
        coll = self._collection(collection)
        start = time.monotonic()
        result = await coll.update_many(filter, update)
        elapsed = time.monotonic() - start
        return QueryResult(
            row_count=result.modified_count,
            duration=elapsed,
        )

    async def delete_many(
        self,
        collection: str,
        filter: Dict[str, Any],
    ) -> QueryResult:
        """批量删除文档。"""
        coll = self._collection(collection)
        start = time.monotonic()
        result = await coll.delete_many(filter)
        elapsed = time.monotonic() - start
        return QueryResult(
            row_count=result.deleted_count,
            duration=elapsed,
        )

    async def aggregate(
        self,
        collection: str,
        pipeline: List[Dict[str, Any]],
    ) -> QueryResult:
        """
        执行聚合管道。

        Args:
            collection: 集合名。
            pipeline: 聚合管道阶段列表。

        Returns:
            聚合结果。
        """
        coll = self._collection(collection)
        start = time.monotonic()
        cursor = coll.aggregate(pipeline)
        docs = await cursor.to_list(length=10000)
        elapsed = time.monotonic() - start
        # 转换 ObjectId
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        return QueryResult(
            rows=docs,
            row_count=len(docs),
            duration=elapsed,
        )

    # ===== 事务（MongoDB 4.0+ 复制集） =====

    async def begin_transaction(self) -> None:
        """MongoDB 事务开始（需要复制集环境）。"""
        logger.warning("MongoDB 事务需要复制集环境，此处使用 session 模拟")
        self._session = await self._ensure_db().client.start_session()
        self._session.start_transaction()

    async def commit(self) -> None:
        if hasattr(self, "_session") and self._session:
            await self._session.commit_transaction()
            await self._session.end_session()
            self._session = None

    async def rollback(self) -> None:
        if hasattr(self, "_session") and self._session:
            await self._session.abort_transaction()
            await self._session.end_session()
            self._session = None

    # ===== 查询分析 =====

    async def explain(self, query: str, params: Any = None) -> ExplainResult:
        """获取 MongoDB 查询执行计划。"""
        import json

        db = self._ensure_db()
        try:
            filter_dict = json.loads(query) if isinstance(query, str) else query
            # 使用 find().explain()
            explanation = await db.command({
                "explain": {"find": "default_collection", "filter": filter_dict},
                "verbosity": "executionStats",
            })
            raw_text = json.dumps(explanation, indent=2, default=str, ensure_ascii=False)
            exec_stats = explanation.get("executionStats", {})
            estimated_rows = exec_stats.get("totalDocsExamined", 0)
            warnings: List[str] = []
            stage = explanation.get("queryPlanner", {}).get("winningPlan", {}).get("stage", "")
            if stage == "COLLSCAN":
                warnings.append("检测到全集合扫描（COLLSCAN）")
            return ExplainResult(
                plan=explanation,
                raw_text=raw_text,
                estimated_rows=float(estimated_rows),
                warnings=warnings,
            )
        except Exception as e:
            return ExplainResult(raw_text=f"获取执行计划失败: {e}", warnings=[str(e)])

    # ===== 元数据 =====

    async def get_tables(self) -> List[str]:
        """获取所有集合名称。"""
        db = self._ensure_db()
        return await db.list_collection_names()

    async def get_columns(self, table: str) -> List[Dict[str, Any]]:
        """MongoDB 无 schema，通过采样文档推断字段。"""
        coll = self._collection(table)
        sample = await coll.find().limit(10).to_list(10)
        fields: Dict[str, str] = {}
        for doc in sample:
            for key, value in doc.items():
                if key not in fields:
                    fields[key] = type(value).__name__
        return [{"name": k, "type": v, "nullable": True, "default": None} for k, v in fields.items()]

    async def get_indexes(self, table: str) -> List[Dict[str, Any]]:
        """获取集合索引信息。"""
        coll = self._collection(table)
        index_info = await coll.index_information()
        return [
            {"name": name, "keys": info.get("key", []), "unique": info.get("unique", False)}
            for name, info in index_info.items()
        ]
