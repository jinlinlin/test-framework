"""
响应验证器 — 策略模式。

职责：根据配置的验证策略组合验证 HTTP 响应。
设计模式：策略模式（Strategy Pattern）
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """
    验证结果数据对象。

    Attributes:
        passed: 是否通过验证。
        message: 验证结果消息。
        errors: 错误详情列表。
    """

    passed: bool = True
    message: str = "OK"
    errors: List[str] = field(default_factory=list)


class ValidationStrategy(ABC):
    """
    验证策略抽象基类。

    所有具体验证策略必须实现 validate 方法。
    """

    @abstractmethod
    async def validate(self, response: Any, case_config: Dict[str, Any]) -> ValidationResult:
        """
        执行验证。

        Args:
            response: HTTP 响应对象。
            case_config: 测试用例配置字典。

        Returns:
            验证结果。
        """
        ...


class StatusCodeStrategy(ValidationStrategy):
    """
    状态码验证策略。

    验证响应状态码是否与预期一致。
    """

    async def validate(self, response: Any, case_config: Dict[str, Any]) -> ValidationResult:
        """
        验证 HTTP 状态码。

        支持预期状态码配置::
            {"expected_status": 200}
            {"expected_status": [200, 201]}

        Args:
            response: HTTP 响应对象。
            case_config: 用例配置。

        Returns:
            验证结果。
        """
        expected = case_config.get("expected_status", 200)
        actual = response.status_code

        # 支持单个状态码或状态码列表
        if isinstance(expected, list):
            if actual not in expected:
                msg = f"状态码不匹配: 期望 {expected}，实际 {actual}"
                return ValidationResult(passed=False, message=msg, errors=[msg])
        else:
            if actual != expected:
                msg = f"状态码不匹配: 期望 {expected}，实际 {actual}"
                return ValidationResult(passed=False, message=msg, errors=[msg])

        return ValidationResult(passed=True, message="状态码验证通过")


class SchemaCheckStrategy(ValidationStrategy):
    """
    Schema 验证策略。

    基于 JSON Schema 验证响应体结构。
    """

    async def validate(self, response: Any, case_config: Dict[str, Any]) -> ValidationResult:
        """
        使用 JSON Schema 验证响应体。

        Args:
            response: HTTP 响应对象。
            case_config: 用例配置，需包含 response_schema 键。

        Returns:
            验证结果。
        """
        schema = case_config.get("response_schema")
        if not schema:
            return ValidationResult(passed=True, message="无 Schema 配置，跳过验证")

        try:
            body = response.json()
        except Exception as e:
            msg = f"响应体无法解析为 JSON: {e}"
            return ValidationResult(passed=False, message=msg, errors=[msg])

        # 使用 jsonschema 库进行验证（延迟导入）
        try:
            import jsonschema
            jsonschema.validate(instance=body, schema=schema)
            return ValidationResult(passed=True, message="Schema 验证通过")
        except ImportError:
            logger.warning("jsonschema 未安装，跳过 Schema 验证")
            return ValidationResult(passed=True, message="jsonschema 未安装，跳过验证")
        except Exception as e:
            msg = f"Schema 验证失败: {e}"
            return ValidationResult(passed=False, message=msg, errors=[msg])


class ContractCheckStrategy(ValidationStrategy):
    """
    契约验证策略。

    对比实际响应与预定义契约（OpenAPI / 契约文件）。
    """

    async def validate(self, response: Any, case_config: Dict[str, Any]) -> ValidationResult:
        """
        对比实际响应与契约定义。

        Args:
            response: HTTP 响应对象。
            case_config: 用例配置，需包含 contract 键。

        Returns:
            验证结果。
        """
        contract = case_config.get("contract")
        if not contract:
            return ValidationResult(passed=True, message="无契约配置，跳过验证")

        errors: List[str] = []

        # 验证响应头
        expected_headers = contract.get("headers", {})
        for header_name, header_value in expected_headers.items():
            actual_value = response.headers.get(header_name)
            if actual_value != header_value:
                errors.append(
                    f"响应头 '{header_name}' 不匹配: "
                    f"期望 '{header_value}'，实际 '{actual_value}'"
                )

        # 验证响应体字段存在性
        expected_fields = contract.get("required_fields", [])
        try:
            body = response.json()
            for fld in expected_fields:
                if fld not in body:
                    errors.append(f"响应体缺少必需字段: '{fld}'")
        except Exception:
            errors.append("响应体无法解析为 JSON，无法验证契约")

        if errors:
            return ValidationResult(
                passed=False,
                message="; ".join(errors),
                errors=errors,
            )
        return ValidationResult(passed=True, message="契约验证通过")


class ResponseTimeStrategy(ValidationStrategy):
    """
    响应时间验证策略。

    验证响应时间是否在可接受范围内。
    """

    async def validate(self, response: Any, case_config: Dict[str, Any]) -> ValidationResult:
        """
        验证响应耗时。

        Args:
            response: HTTP 响应对象（需有 elapsed 属性）。
            case_config: 用例配置，需包含 max_response_time（毫秒）。

        Returns:
            验证结果。
        """
        max_time = case_config.get("max_response_time")  # 毫秒
        if max_time is None:
            return ValidationResult(passed=True, message="无响应时间限制，跳过验证")

        # httpx 响应有 elapsed 属性
        elapsed_ms = response.elapsed.total_seconds() * 1000 if hasattr(response, "elapsed") else 0

        if elapsed_ms > max_time:
            msg = f"响应时间超限: {elapsed_ms:.1f}ms > {max_time}ms"
            return ValidationResult(passed=False, message=msg, errors=[msg])

        return ValidationResult(passed=True, message=f"响应时间验证通过: {elapsed_ms:.1f}ms")


class ResponseValidator:
    """
    响应验证器（策略模式）。

    根据配置组合多种验证策略，对 HTTP 响应进行全面验证。

    Attributes:
        _strategies: 验证策略列表。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化响应验证器，根据配置加载验证策略。

        Args:
            config: 引擎配置字典。
        """
        self._strategies: List[ValidationStrategy] = []

        validation_config = config.get("validation", {})

        # 始终包含状态码验证
        self._strategies.append(StatusCodeStrategy())

        # 按需加载 Schema 验证
        if validation_config.get("schema_check", False):
            self._strategies.append(SchemaCheckStrategy())

        # 按需加载契约验证
        if validation_config.get("contract_check", False):
            self._strategies.append(ContractCheckStrategy())

        # 按需加载响应时间验证
        if validation_config.get("response_time_check", False):
            self._strategies.append(ResponseTimeStrategy())

    async def validate(self, response: Any, case_config: Dict[str, Any]) -> ValidationResult:
        """
        依次执行所有验证策略，汇总结果。

        Args:
            response: HTTP 响应对象。
            case_config: 测试用例配置字典。

        Returns:
            汇总后的验证结果。
        """
        all_errors: List[str] = []

        for strategy in self._strategies:
            result = await strategy.validate(response, case_config)
            if not result.passed:
                all_errors.extend(result.errors)

        if all_errors:
            return ValidationResult(
                passed=False,
                message="; ".join(all_errors),
                errors=all_errors,
            )

        return ValidationResult(passed=True, message="所有验证通过")
