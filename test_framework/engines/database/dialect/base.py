"""
数据库方言抽象基类 — 策略模式。

职责：屏蔽不同数据库（PostgreSQL / MySQL / MongoDB / Redis）的 SQL 和协议差异，
      为上层引擎提供统一的连接、查询、执行计划分析接口。

设计模式：策略模式（Strategy Pattern）
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

logger = logging.getLogger(__name__)


class Dialect(ABC):
    """
    数据库方言抽象基类。

    每种数据库（PostgreSQL / MySQL / MongoDB / Redis）实现一个具体方言类，
    负责处理连接创建、SQL 生成、执行计划解析等数据库特有逻辑。

    Attributes:
        _name: 方言名称。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """方言名称（如 'postgresql' / 'mysql'）。"""
        ...

    @abstractmethod
    def build_explain_query(self, sql: str) -> str:
        """
        构建执行计划分析查询语句。

        不同数据库使用不同的 EXPLAIN 语法。

        Args:
            sql: 原始 SQL 查询。

        Returns:
            包含 EXPLAIN 前缀的分析查询语句。
        """
        ...

    @abstractmethod
    def parse_explain_result(self, result: Any) -> Dict[str, Any]:
        """
        解析执行计划结果，转换为统一格式。

        Args:
            result: 数据库返回的原始执行计划结果。

        Returns:
            统一格式的执行计划字典，包含以下键：
            - plan_type: 扫描类型（SeqScan / IndexScan / ...）
            - estimated_cost: 预估代价
            - estimated_rows: 预估行数
            - actual_rows: 实际行数
            - tables: 涉及的表
            - indexes_used: 使用的索引
            - warnings: 告警信息
        """
        ...

    @abstractmethod
    def get_connection_string(self, config: Dict[str, Any]) -> str:
        """
        根据配置生成连接字符串。

        Args:
            config: 数据库连接配置（host / port / database / user / password）。

        Returns:
            数据库连接字符串。
        """
        ...

    @abstractmethod
    async def create_connection(self, conn_str: str) -> Any:
        """
        创建数据库连接。

        Args:
            conn_str: 连接字符串。

        Returns:
            数据库连接对象。
        """
        ...

    @abstractmethod
    async def close_connection(self, conn: Any) -> None:
        """
        关闭数据库连接。

        Args:
            conn: 数据库连接对象。
        """
        ...

    @abstractmethod
    async def execute_query(self, conn: Any, query: str, params: Any = None) -> Any:
        """
        执行查询并返回结果。

        Args:
            conn: 数据库连接。
            query: 查询语句。
            params: 查询参数。

        Returns:
            查询结果。
        """
        ...

    def build_benchmark_query(self, sql: str, iterations: int = 1) -> str:
        """
        构建基准测试查询（默认返回原始 SQL）。

        部分数据库可能需要特殊的基准测试包装。

        Args:
            sql: 原始 SQL。
            iterations: 迭代次数。

        Returns:
            基准测试查询语句。
        """
        return sql


class DialectFactory:
    """
    数据库方言工厂（工厂模式）。

    根据数据库类型名称创建对应的方言实例。

    Attributes:
        _registry: 数据库类型 → 方言类的映射表。
    """

    _registry: Dict[str, Type[Dialect]] = {}

    @classmethod
    def register(cls, db_type: str, dialect_cls: Type[Dialect]) -> None:
        """
        注册方言类。

        Args:
            db_type: 数据库类型名称（如 'postgresql'）。
            dialect_cls: 方言类。
        """
        cls._registry[db_type.lower()] = dialect_cls
        logger.debug(f"注册数据库方言: {db_type} → {dialect_cls.__name__}")

    @classmethod
    def create(cls, db_type: str) -> Dialect:
        """
        根据数据库类型创建方言实例。

        Args:
            db_type: 数据库类型名称。

        Returns:
            方言实例。

        Raises:
            ValueError: 不支持的数据库类型。
        """
        dialect_cls = cls._registry.get(db_type.lower())
        if dialect_cls is None:
            raise ValueError(
                f"不支持的数据库类型: {db_type}，"
                f"已注册: {list(cls._registry.keys())}"
            )
        return dialect_cls()

    @classmethod
    def available_dialects(cls) -> list:
        """返回已注册的所有数据库类型。"""
        return list(cls._registry.keys())


# ===== 自动注册内置方言 =====
def _auto_register() -> None:
    """模块导入时自动注册内置方言。"""
    from .postgresql import PostgreSQLDialect
    from .mysql import MySQLDialect
    from .mongodb import MongoDBDialect
    from .redis import RedisDialect

    DialectFactory.register("postgresql", PostgreSQLDialect)
    DialectFactory.register("postgres", PostgreSQLDialect)
    DialectFactory.register("mysql", MySQLDialect)
    DialectFactory.register("mongodb", MongoDBDialect)
    DialectFactory.register("mongo", MongoDBDialect)
    DialectFactory.register("redis", RedisDialect)


_auto_register()
