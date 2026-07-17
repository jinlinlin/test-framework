"""
被测系统模型 — 定义被测目标系统的连接和认证信息。

TargetSystem 描述了被测服务的地址、协议、认证方式等，
由引擎在 setup() 阶段使用，用于建立连接和发送请求。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TargetSystem:
    """
    被测系统数据模型。

    Attributes:
        id: 系统唯一标识符（如 'system_a'），用于配置关联。
        name: 系统可读名称（如 '用户服务 - 测试环境'）。
        base_url: HTTP 基础 URL（如 'http://localhost:8080'），REST/Web 测试使用。
        host: 主机地址（IP 或域名）。
        port: 端口号。
        protocol: 通信协议（http/https/grpc/tcp）。
        auth: 认证配置字典（如 {"type": "bearer", "token_env": "SYSTEM_A_TOKEN"}）。
        metadata: 扩展元数据（如技术栈、版本号等）。
    """

    id: str
    name: str
    base_url: Optional[str] = None
    host: str = "localhost"
    port: int = 8080
    protocol: str = "http"
    auth: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_connection_string(self) -> str:
        """
        生成连接字符串。

        对于 HTTP/HTTPS 协议返回 base_url，
        对于其他协议返回 host:port 格式。

        Returns:
            连接字符串。
        """
        if self.base_url:
            return self.base_url
        return f"{self.protocol}://{self.host}:{self.port}"

    def to_dict(self) -> Dict[str, Any]:
        """将系统信息序列化为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "auth": self.auth,
            "metadata": self.metadata,
        }
