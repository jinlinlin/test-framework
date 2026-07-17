"""engines.database.dialect 包 — 数据库方言（策略模式）。"""
from .base import Dialect, DialectFactory
from .postgresql import PostgreSQLDialect
from .mysql import MySQLDialect
from .mongodb import MongoDBDialect
from .redis import RedisDialect

__all__ = [
    "Dialect",
    "DialectFactory",
    "PostgreSQLDialect",
    "MySQLDialect",
    "MongoDBDialect",
    "RedisDialect",
]
