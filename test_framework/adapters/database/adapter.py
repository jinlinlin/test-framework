"""
数据库适配器统一接口。

职责：定义数据库操作的统一抽象，
      包含连接管理、CRUD 操作、事务、查询分析等方法。
      支持 PostgreSQL / MySQL / MongoDB / Redis 四种数据库类型。
"""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..base import BaseAdapter


@dataclass
class QueryResult:
    """
    查询结果数据对象。

    Attributes:
        rows: 结果行列表。
        columns: 列名列表。
        row_count: 影响行数（INSERT / UPDATE / DELETE 时有效）。
        duration: 查询耗时（秒）。
        raw: 原始响应（不同数据库格式不同）。
    """

    rows: List[Any] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    row_count: int = 0
    duration: float = 0.0
    raw: Any = None

    def fetch_one(self) -> Optional[Any]:
        """获取第一行结果。"""
        return self.rows[0] if self.rows else None

    def fetch_all(self) -> List[Any]:
        """获取所有结果行。"""
        return list(self.rows)

    @property
    def is_empty(self) -> bool:
        """结果集是否为空。"""
        return len(self.rows) == 0


@dataclass
class ExplainResult:
    """
    执行计划结果。

    Attributes:
        plan: 执行计划数据（字典或列表，取决于数据库类型）。
        raw_text: 原始执行计划文本。
        total_cost: 预估总代价。
        estimated_rows: 预估行数。
        warnings: 告警信息列表。
    """

    plan: Any = None
    raw_text: str = ""
    total_cost: float = 0.0
    estimated_rows: float = 0.0
    warnings: List[str] = field(default_factory=list)


class DatabaseAdapter(BaseAdapter):
    """
    数据库适配器抽象基类。

    定义连接管理、CRUD 操作、事务、查询分析等统一方法。
    """

    @property
    def adapter_type(self) -> str:
        return "database"

    # ===== 基本查询 =====

    @abstractmethod
    async def execute(self, query: str, params: Any = None) -> QueryResult:
        """
        执行 SQL 查询/命令。

        Args:
            query: SQL 查询字符串。
            params: 查询参数（列表或字典，取决于数据库类型）。

        Returns:
            查询结果。
        """
        ...

    @abstractmethod
    async def execute_many(self, query: str, params_list: List[Any]) -> QueryResult:
        """
        批量执行 SQL（批量 INSERT 等）。

        Args:
            query: SQL 查询模板。
            params_list: 参数列表。

        Returns:
            执行结果。
        """
        ...

    # ===== CRUD 便捷方法 =====

    async def insert(self, table: str, data: Dict[str, Any]) -> QueryResult:
        """
        插入一行数据。

        Args:
            table: 表名。
            data: 列名→值映射字典。

        Returns:
            插入结果。
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join([f"${i+1}" for i in range(len(data))])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        return await self.execute(query, list(data.values()))

    async def select(
        self,
        table: str,
        where: Optional[str] = None,
        params: Any = None,
        limit: int = 100,
        order_by: str = "",
    ) -> QueryResult:
        """
        查询数据。

        Args:
            table: 表名。
            where: WHERE 条件（不含 WHERE 关键字）。
            params: 查询参数。
            limit: 返回行数限制。
            order_by: ORDER BY 表达式。

        Returns:
            查询结果。
        """
        query = f"SELECT * FROM {table}"
        if where:
            query += f" WHERE {where}"
        if order_by:
            query += f" ORDER BY {order_by}"
        query += f" LIMIT {limit}"
        return await self.execute(query, params)

    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        where: str,
        params: Any = None,
    ) -> QueryResult:
        """
        更新数据。

        Args:
            table: 表名。
            data: 更新的列名→值映射。
            where: WHERE 条件。
            params: WHERE 参数。

        Returns:
            更新结果。
        """
        set_clause = ", ".join([f"{k} = ${i+1}" for i, k in enumerate(data.keys())])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        all_params = list(data.values())
        if params:
            all_params.extend(params if isinstance(params, list) else [params])
        return await self.execute(query, all_params)

    async def delete(self, table: str, where: str, params: Any = None) -> QueryResult:
        """
        删除数据。

        Args:
            table: 表名。
            where: WHERE 条件。
            params: WHERE 参数。

        Returns:
            删除结果。
        """
        query = f"DELETE FROM {table} WHERE {where}"
        return await self.execute(query, params)

    # ===== 事务 =====

    @abstractmethod
    async def begin_transaction(self) -> None:
        """开始事务。"""
        ...

    @abstractmethod
    async def commit(self) -> None:
        """提交事务。"""
        ...

    @abstractmethod
    async def rollback(self) -> None:
        """回滚事务。"""
        ...

    # ===== 查询分析 =====

    @abstractmethod
    async def explain(self, query: str, params: Any = None) -> ExplainResult:
        """
        获取查询执行计划。

        Args:
            query: SQL 查询。
            params: 查询参数。

        Returns:
            执行计划结果。
        """
        ...

    # ===== 元数据 =====

    @abstractmethod
    async def get_tables(self) -> List[str]:
        """获取数据库中所有表名。"""
        ...

    @abstractmethod
    async def get_columns(self, table: str) -> List[Dict[str, Any]]:
        """
        获取表的列信息。

        Args:
            table: 表名。

        Returns:
            列信息列表，每项包含 name/type/nullable/default 等。
        """
        ...

    @abstractmethod
    async def get_indexes(self, table: str) -> List[Dict[str, Any]]:
        """
        获取表的索引信息。

        Args:
            table: 表名。

        Returns:
            索引信息列表。
        """
        ...
