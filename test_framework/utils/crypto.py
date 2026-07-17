"""
加密工具 — 提供哈希、签名、编解码等安全相关操作。

职责：封装常用的加密操作（MD5/SHA/HMAC/Base64/JWT），
      所有外部依赖使用延迟导入。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import string
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CryptoUtils:
    """
    加密工具类。

    使用示例::

        crypto = CryptoUtils()
        hash_val = crypto.sha256("hello world")
        token = crypto.generate_token(32)
        encoded = crypto.base64_encode(b"data")
    """

    # ------------------------------------------------------------------
    # 哈希
    # ------------------------------------------------------------------

    @staticmethod
    def md5(data: str, encoding: str = "utf-8") -> str:
        """计算 MD5 哈希。"""
        return hashlib.md5(data.encode(encoding)).hexdigest()

    @staticmethod
    def sha256(data: str, encoding: str = "utf-8") -> str:
        """计算 SHA-256 哈希。"""
        return hashlib.sha256(data.encode(encoding)).hexdigest()

    @staticmethod
    def sha512(data: str, encoding: str = "utf-8") -> str:
        """计算 SHA-512 哈希。"""
        return hashlib.sha512(data.encode(encoding)).hexdigest()

    @staticmethod
    def hmac_sha256(key: str, message: str, encoding: str = "utf-8") -> str:
        """计算 HMAC-SHA256。"""
        return hmac.new(
            key.encode(encoding),
            message.encode(encoding),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def file_hash(file_path: str, algorithm: str = "sha256") -> str:
        """
        计算文件的哈希值。

        Args:
            file_path: 文件路径。
            algorithm: 哈希算法（md5 / sha256 / sha512）。

        Returns:
            十六进制哈希字符串。
        """
        h = hashlib.new(algorithm)
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Base64
    # ------------------------------------------------------------------

    @staticmethod
    def base64_encode(data: bytes) -> str:
        """Base64 编码。"""
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def base64_decode(data: str) -> bytes:
        """Base64 解码。"""
        return base64.b64decode(data)

    @staticmethod
    def base64url_encode(data: bytes) -> str:
        """URL 安全的 Base64 编码。"""
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    # ------------------------------------------------------------------
    # 令牌生成
    # ------------------------------------------------------------------

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """生成安全随机令牌。"""
        return secrets.token_hex(length // 2)

    @staticmethod
    def generate_password(length: int = 16) -> str:
        """生成随机密码（含大小写字母、数字、特殊字符）。"""
        charset = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(secrets.choice(charset) for _ in range(length))

    @staticmethod
    def generate_api_key(prefix: str = "tf") -> str:
        """生成 API Key（带前缀）。"""
        key = secrets.token_urlsafe(24)
        return f"{prefix}_{key}"

    # ------------------------------------------------------------------
    # JWT（延迟导入）
    # ------------------------------------------------------------------

    @staticmethod
    def jwt_encode(
        payload: Dict[str, Any], secret: str, algorithm: str = "HS256"
    ) -> str:
        """
        JWT 编码（需要 PyJWT）。

        Args:
            payload: 载荷字典。
            secret: 签名密钥。
            algorithm: 签名算法。

        Returns:
            JWT 字符串。
        """
        try:
            import jwt
            return jwt.encode(payload, secret, algorithm=algorithm)
        except ImportError:
            logger.error("PyJWT 未安装，无法编码 JWT")
            raise

    @staticmethod
    def jwt_decode(
        token: str, secret: str, algorithms: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        JWT 解码（需要 PyJWT）。

        Args:
            token: JWT 字符串。
            secret: 签名密钥。
            algorithms: 允许的算法列表。

        Returns:
            解码后的载荷字典。
        """
        try:
            import jwt
            return jwt.decode(token, secret, algorithms=algorithms or ["HS256"])
        except ImportError:
            logger.error("PyJWT 未安装，无法解码 JWT")
            raise
