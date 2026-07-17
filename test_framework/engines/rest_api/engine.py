"""
REST API 测试引擎 — Python 引擎主类。

职责：基于 httpx 实现异步 HTTP 请求，支持接口自动构建、
      权限认证、限流控制、契约校验、Schema 验证。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from ...core.models import TestCase, TestMetrics, TestResult, TargetSystem
from ...core.models.enums import TestStatus, TestType
from ..base import BaseEngine
from .auth_handler import AuthHandler
from .rate_limiter import RateLimiter
from .request_builder import RequestBuilder
from .response_validator import ResponseValidator
from .schema_validator import SchemaValidator

logger = logging.getLogger(__name__)


class RestAPIEngine(BaseEngine):
    """
    REST API 测试引擎。

    支持单接口测试、批量测试、接口压测，
    集成认证、限流、Schema 验证、契约测试。

    Attributes:
        _client: httpx 异步客户端。
        _auth_handler: 认证处理器。
        _rate_limiter: 限流器。
        _schema_validator: Schema 验证器。
    """

    def __init__(self, config: Dict[str, Any], container: Any) -> None:
        """初始化 REST API 引擎。"""
        super().__init__(config, container)
        self._client: Optional[Any] = None
        self._auth_handler = AuthHandler(config.get("auth", {}))
        self._rate_limiter = RateLimiter(config.get("rate_limit", {}))
        self._schema_validator = SchemaValidator()

    @property
    def engine_type(self) -> TestType:
        return TestType.REST_API

    async def setup(self, target: TargetSystem) -> None:
        """初始化 HTTP 客户端和认证。"""
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=target.base_url,
                timeout=self._config.get("timeout", 30),
                verify=self._config.get("verify_ssl", True),
                follow_redirects=self._config.get("follow_redirects", True),
            )
            # 初始化认证
            auth_config = getattr(target, "auth", None) or {}
            await self._auth_handler.initialize(auth_config)
            logger.info(f"REST API 引擎已初始化: {target.base_url}")
        except ImportError:
            logger.error("httpx 未安装")
            raise

    async def execute_case(self, case: TestCase, target: TargetSystem) -> TestResult:
        """执行单个 API 测试用例。"""
        try:
            # 构建请求
            builder = RequestBuilder.from_config(case.config)
            request = builder.build()

            # 获取认证头
            auth_headers = await self._auth_handler.get_auth_headers()

            # 限流
            await self._rate_limiter.acquire()

            # 发送请求
            start = time.monotonic()
            response = await self._client.request(
                method=request.method,
                url=request.path,
                headers={**auth_headers, **request.headers},
                params=request.params,
                json=request.body,
            )
            duration = time.monotonic() - start

            # 验证响应
            validator = ResponseValidator(self._config)
            validation = await validator.validate(response, case.config)

            status = TestStatus.PASS if validation.passed else TestStatus.FAIL

            # 尝试解析响应体
            try:
                response_body = response.json()
            except Exception:
                response_body = response.text

            return TestResult(
                case_id=case.id,
                status=status,
                duration=duration,
                details={
                    "status_code": response.status_code,
                    "response_body": response_body,
                    "validation": validation.message,
                },
                metrics=TestMetrics(
                    latency_avg=duration * 1000,
                    throughput=1 / duration if duration > 0 else 0,
                ),
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"API 测试异常: {e}")
            return TestResult(
                case_id=case.id,
                status=TestStatus.ERROR,
                duration=0,
                details={"error": str(e)},
                metrics=TestMetrics(),
                timestamp=datetime.now(),
            )

    async def collect_metrics(self) -> TestMetrics:
        """汇总 API 测试指标。"""
        if not self._results:
            return TestMetrics()
        avg_latency = sum(r.metrics.latency_avg for r in self._results) / len(self._results)
        return TestMetrics(
            total_cases=len(self._results),
            passed=sum(1 for r in self._results if r.status == TestStatus.PASS),
            failed=sum(1 for r in self._results if r.status == TestStatus.FAIL),
            latency_avg=avg_latency,
        )

    async def teardown(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._client:
            await self._client.aclose()
            logger.info("REST API 引擎已关闭")
