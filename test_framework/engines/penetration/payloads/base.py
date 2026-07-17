"""
攻击载荷抽象基类 — 策略模式。

职责：定义攻击载荷的统一接口，所有具体载荷
      （SQL 注入 / XSS / 路径遍历 / 命令注入 / SSRF / XXE）继承此类。

设计模式：策略模式（Strategy Pattern）
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Payload(ABC):
    """
    攻击载荷抽象基类。

    每种攻击类型实现一个具体载荷类，提供：
    - generate(): 生成攻击载荷列表
    - get_detection_patterns(): 返回检测特征模式

    Attributes:
        name: 载荷名称。
        severity: 严重等级（low / medium / high / critical）。
        category: 攻击类别。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """载荷名称标识。"""
        ...

    @property
    @abstractmethod
    def severity(self) -> str:
        """严重等级：low / medium / high / critical。"""
        ...

    @property
    def category(self) -> str:
        """攻击类别。"""
        return self.name

    @abstractmethod
    def generate(self, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        生成攻击载荷列表。

        Args:
            params: 可选的生成参数。

        Returns:
            攻击载荷字符串列表。
        """
        ...

    @abstractmethod
    def get_detection_patterns(self) -> List[str]:
        """
        获取漏洞检测特征模式。

        这些模式用于在响应体中搜索，判断漏洞是否存在。

        Returns:
            特征模式字符串列表。
        """
        ...

    def get_description(self) -> str:
        """获取载荷描述。"""
        return f"{self.name} 攻击载荷（{self.severity}）"
