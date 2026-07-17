"""
认证处理器 — 统一 HTTP 认证管理。

职责：支持 Basic / Bearer / OAuth2 / API Key 四种认证方式，
      统一管理认证头的生成与刷新。
"""
from __future__ import annotations

import base64
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AuthHandler:
    """
    认证处理器。

    根据配置的认证类型，自动生成对应的 HTTP 认证头。
    支持 Basic / Bearer / OAuth2 / API Key 四种认证方式。

    Attributes:
        _config: 引擎级认证默认配置。
        _auth_type: 当前认证类型。
        _credentials: 当前认证凭据。
        _token: OAuth2 访问令牌。
        _token_expiry: 令牌过期时间戳。
    """

    # 认证类型常量
    AUTH_BASIC = "basic"
    AUTH_BEARER = "bearer"
    AUTH_OAUTH2 = "oauth2"
    AUTH_API_KEY = "api_key"

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化认证处理器。

        Args:
            config: 引擎级认证默认配置，可被 target 级配置覆盖。
        """
        self._config = config
        self._auth_type: Optional[str] = None
        self._credentials: Dict[str, Any] = {}
        self._token: Optional[str] = None
        self._token_expiry: float = 0

    async def initialize(self, auth_config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化认证信息，合并引擎默认配置和目标系统配置。

        配置格式示例::

            {
                "type": "bearer",
                "token": "your-access-token"
            }

            {
                "type": "basic",
                "username": "admin",
                "password": "secret"
            }

            {
                "type": "oauth2",
                "client_id": "xxx",
                "client_secret": "yyy",
                "token_url": "https://auth.example.com/token",
                "scope": "read write"
            }

            {
                "type": "api_key",
                "key_name": "X-API-Key",
                "key_value": "your-api-key",
                "location": "header"  # header 或 query
            }

        Args:
            auth_config: 目标系统级认证配置，会覆盖引擎默认配置。
        """
        # 合并配置：目标系统配置优先
        merged = {**self._config}
        if auth_config:
            merged.update(auth_config)

        self._auth_type = merged.get("type", "").lower()
        self._credentials = merged

        # 如果是 OAuth2，预获取令牌
        if self._auth_type == self.AUTH_OAUTH2:
            await self._fetch_oauth2_token()

        logger.debug(f"认证处理器已初始化: type={self._auth_type}")

    async def get_auth_headers(self) -> Dict[str, str]:
        """
        获取当前认证头。

        Returns:
            包含认证信息的请求头字典。若未配置认证则返回空字典。
        """
        if not self._auth_type:
            return {}

        if self._auth_type == self.AUTH_BASIC:
            return self._build_basic_header()

        if self._auth_type == self.AUTH_BEARER:
            return self._build_bearer_header()

        if self._auth_type == self.AUTH_OAUTH2:
            # 检查令牌是否过期，过期则刷新
            if self._is_token_expired():
                await self.refresh_token()
            return self._build_oauth2_header()

        if self._auth_type == self.AUTH_API_KEY:
            return self._build_api_key_header()

        logger.warning(f"未知的认证类型: {self._auth_type}")
        return {}

    async def refresh_token(self) -> None:
        """
        刷新 OAuth2 访问令牌。

        当令牌过期时自动调用，重新获取访问令牌。
        """
        if self._auth_type == self.AUTH_OAUTH2:
            await self._fetch_oauth2_token()
            logger.info("OAuth2 令牌已刷新")

    # ===== 私有方法 =====

    def _build_basic_header(self) -> Dict[str, str]:
        """构建 Basic 认证头。"""
        username = self._credentials.get("username", "")
        password = self._credentials.get("password", "")
        raw = f"{username}:{password}"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {encoded}"}

    def _build_bearer_header(self) -> Dict[str, str]:
        """构建 Bearer 认证头。"""
        token = self._credentials.get("token", "")
        return {"Authorization": f"Bearer {token}"}

    def _build_oauth2_header(self) -> Dict[str, str]:
        """构建 OAuth2 认证头。"""
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    def _build_api_key_header(self) -> Dict[str, str]:
        """构建 API Key 认证头。"""
        key_name = self._credentials.get("key_name", "X-API-Key")
        key_value = self._credentials.get("key_value", "")
        return {key_name: key_value}

    def _is_token_expired(self) -> bool:
        """检查 OAuth2 令牌是否已过期。"""
        if not self._token:
            return True
        # 预留 60 秒安全边距
        return time.time() >= (self._token_expiry - 60)

    async def _fetch_oauth2_token(self) -> None:
        """
        通过 OAuth2 Client Credentials 流程获取令牌。

        向 token_url 发送 POST 请求获取访问令牌。
        """
        token_url = self._credentials.get("token_url", "")
        client_id = self._credentials.get("client_id", "")
        client_secret = self._credentials.get("client_secret", "")
        scope = self._credentials.get("scope", "")

        if not token_url:
            logger.warning("OAuth2 未配置 token_url，使用静态 token")
            self._token = self._credentials.get("token", "")
            self._token_expiry = time.time() + 3600
            return

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "scope": scope,
                    },
                )
                data = response.json()
                self._token = data.get("access_token", "")
                expires_in = data.get("expires_in", 3600)
                self._token_expiry = time.time() + expires_in
                logger.info(f"OAuth2 令牌已获取，有效期 {expires_in}s")

        except ImportError:
            logger.error("httpx 未安装，无法执行 OAuth2 令牌获取")
            self._token = self._credentials.get("token", "")
            self._token_expiry = time.time() + 3600
        except Exception as e:
            logger.error(f"OAuth2 令牌获取失败: {e}")
            self._token = self._credentials.get("token", "")
            self._token_expiry = time.time() + 3600
