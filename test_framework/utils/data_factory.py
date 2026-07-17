"""
数据工厂 — 生成测试用的随机数据。

职责：提供常见数据类型的随机生成方法（字符串、数字、邮箱、
      JSON 对象、CSV 行等），支持自定义模板。
"""
from __future__ import annotations

import logging
import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class DataFactory:
    """
    数据工厂 — 生成测试用的随机数据。

    使用示例::

        factory = DataFactory(seed=42)
        name = factory.random_string(10)
        email = factory.random_email()
        users = factory.random_list(100, factory.random_dict)
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        """
        初始化数据工厂。

        Args:
            seed: 随机种子（设置后可复现）。
        """
        if seed is not None:
            random.seed(seed)

    # ------------------------------------------------------------------
    # 基础类型
    # ------------------------------------------------------------------

    def random_string(self, length: int = 8, charset: Optional[str] = None) -> str:
        """生成随机字符串。"""
        chars = charset or (string.ascii_letters + string.digits)
        return "".join(random.choice(chars) for _ in range(length))

    def random_int(self, min_val: int = 0, max_val: int = 10000) -> int:
        """生成随机整数。"""
        return random.randint(min_val, max_val)

    def random_float(self, min_val: float = 0.0, max_val: float = 100.0, decimals: int = 2) -> float:
        """生成随机浮点数。"""
        return round(random.uniform(min_val, max_val), decimals)

    def random_bool(self) -> bool:
        """生成随机布尔值。"""
        return random.choice([True, False])

    def random_uuid(self) -> str:
        """生成 UUID 字符串。"""
        return str(uuid.uuid4())

    # ------------------------------------------------------------------
    # 复合类型
    # ------------------------------------------------------------------

    def random_email(self, domain: str = "example.com") -> str:
        """生成随机邮箱地址。"""
        username = self.random_string(8, string.ascii_lowercase)
        return f"{username}@{domain}"

    def random_phone(self, prefix: str = "138") -> str:
        """生成随机手机号。"""
        suffix = self.random_string(8, string.digits)
        return f"{prefix}{suffix}"

    def random_url(self, domain: str = "example.com") -> str:
        """生成随机 URL。"""
        path = self.random_string(6, string.ascii_lowercase)
        return f"https://{domain}/{path}"

    def random_datetime(
        self, start: Optional[datetime] = None, end: Optional[datetime] = None
    ) -> datetime:
        """生成随机日期时间。"""
        start = start or datetime(2020, 1, 1)
        end = end or datetime.now()
        delta = (end - start).total_seconds()
        random_offset = random.uniform(0, delta)
        return start + timedelta(seconds=random_offset)

    def random_dict(
        self,
        template: Optional[Dict[str, Callable]] = None,
    ) -> Dict[str, Any]:
        """
        生成随机字典。

        Args:
            template: 字段名 -> 生成函数的模板。
                      例如 ``{"name": lambda: self.random_string(5)}``

        Returns:
            随机生成的字典。
        """
        if template:
            return {key: gen() for key, gen in template.items()}

        # 默认模板
        return {
            "id": self.random_uuid(),
            "name": self.random_string(8),
            "email": self.random_email(),
            "age": self.random_int(18, 80),
            "active": self.random_bool(),
        }

    def random_list(
        self, count: int, generator: Optional[Callable] = None
    ) -> List[Any]:
        """
        生成随机列表。

        Args:
            count: 元素数量。
            generator: 元素生成函数（默认使用 random_dict）。

        Returns:
            随机元素列表。
        """
        gen = generator or self.random_dict
        return [gen() for _ in range(count)]

    # ------------------------------------------------------------------
    # 结构化数据
    # ------------------------------------------------------------------

    def random_json(self, depth: int = 2) -> Dict[str, Any]:
        """生成随机嵌套 JSON 对象。"""
        if depth <= 0:
            return {"value": self.random_string(4)}

        return {
            "id": self.random_uuid(),
            "field": self.random_string(5),
            "nested": self.random_json(depth - 1),
            "items": [self.random_string(3) for _ in range(self.random_int(1, 5))],
        }

    def random_csv_row(self, columns: List[str]) -> Dict[str, str]:
        """生成一行随机 CSV 数据。"""
        row: Dict[str, str] = {}
        for col in columns:
            if "id" in col.lower():
                row[col] = self.random_uuid()
            elif "email" in col.lower():
                row[col] = self.random_email()
            elif "name" in col.lower():
                row[col] = self.random_string(8)
            elif "age" in col.lower():
                row[col] = str(self.random_int(18, 80))
            else:
                row[col] = self.random_string(6)
        return row
