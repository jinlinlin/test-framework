"""
契约测试器 — 对比实际响应与预定义契约。

职责：加载并验证 API 契约（OpenAPI / 自定义契约文件），
      对比实际 HTTP 响应与契约定义，发现接口变更和回归。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ContractViolation:
    """
    契约违规记录。

    Attributes:
        field_path: 违规字段路径（如 'body.data.id'）。
        expected: 契约期望值。
        actual: 实际值。
        violation_type: 违规类型（missing_field / type_mismatch / value_mismatch）。
        message: 违规描述。
    """

    field_path: str = ""
    expected: Any = None
    actual: Any = None
    violation_type: str = ""
    message: str = ""


@dataclass
class ContractResult:
    """
    契约测试结果。

    Attributes:
        passed: 是否通过契约验证。
        violations: 违规记录列表。
        message: 测试结果消息。
    """

    passed: bool = True
    violations: List[ContractViolation] = field(default_factory=list)
    message: str = "契约验证通过"


class ContractTester:
    """
    契约测试器。

    加载预定义契约（JSON 文件或字典），对比实际 API 响应
    与契约定义，检测字段缺失、类型不匹配、值不一致等问题。

    Attributes:
        _contracts: 端点路径 → 契约定义的映射表。
    """

    def __init__(self) -> None:
        """初始化契约测试器。"""
        self._contracts: Dict[str, Dict[str, Any]] = {}

    def load_contract(self, contract_path: str) -> None:
        """
        从 JSON 文件加载契约定义。

        契约文件格式::

            {
                "/api/users": {
                    "GET": {
                        "status_code": 200,
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "type": "object",
                            "required_fields": ["id", "name", "email"],
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "string"},
                                "email": {"type": "string"}
                            }
                        }
                    }
                }
            }

        Args:
            contract_path: 契约 JSON 文件路径。

        Raises:
            FileNotFoundError: 契约文件不存在。
            json.JSONDecodeError: 文件格式错误。
        """
        path = Path(contract_path)
        if not path.exists():
            logger.error(f"契约文件不存在: {contract_path}")
            raise FileNotFoundError(f"契约文件不存在: {contract_path}")

        with open(path, "r", encoding="utf-8") as f:
            contracts = json.load(f)

        self._contracts.update(contracts)
        logger.info(f"已加载契约文件: {contract_path}，含 {len(contracts)} 个端点")

    def load_contract_from_dict(self, contracts: Dict[str, Any]) -> None:
        """
        从字典加载契约定义。

        Args:
            contracts: 契约定义字典。
        """
        self._contracts.update(contracts)
        logger.info(f"已加载契约定义，含 {len(contracts)} 个端点")

    async def validate(self, response: Any, endpoint: str, method: str = "GET") -> ContractResult:
        """
        验证实际响应是否符合契约定义。

        Args:
            response: HTTP 响应对象（httpx.Response）。
            endpoint: 端点路径（如 '/api/users'）。
            method: HTTP 方法。

        Returns:
            契约测试结果。
        """
        # 查找端点契约
        endpoint_contract = self._contracts.get(endpoint, {})
        method_contract = endpoint_contract.get(method.upper(), {})

        if not method_contract:
            return ContractResult(
                passed=True,
                message=f"端点 {method} {endpoint} 无契约定义，跳过验证",
            )

        violations: List[ContractViolation] = []

        # 1. 验证状态码
        expected_status = method_contract.get("status_code")
        if expected_status is not None and response.status_code != expected_status:
            violations.append(ContractViolation(
                field_path="status_code",
                expected=expected_status,
                actual=response.status_code,
                violation_type="value_mismatch",
                message=f"状态码不匹配: 期望 {expected_status}，实际 {response.status_code}",
            ))

        # 2. 验证响应头
        expected_headers = method_contract.get("headers", {})
        for header_name, expected_value in expected_headers.items():
            actual_value = response.headers.get(header_name, "")
            # 响应头值做包含匹配（因可能带 charset 等后缀）
            if expected_value not in actual_value:
                violations.append(ContractViolation(
                    field_path=f"headers.{header_name}",
                    expected=expected_value,
                    actual=actual_value,
                    violation_type="value_mismatch",
                    message=f"响应头 '{header_name}' 不匹配: 期望含 '{expected_value}'，实际 '{actual_value}'",
                ))

        # 3. 验证响应体
        body_contract = method_contract.get("body", {})
        if body_contract:
            try:
                body = response.json()
                body_violations = self._validate_body(body, body_contract, "body")
                violations.extend(body_violations)
            except Exception as e:
                violations.append(ContractViolation(
                    field_path="body",
                    expected="valid JSON",
                    actual=str(e),
                    violation_type="type_mismatch",
                    message=f"响应体无法解析为 JSON: {e}",
                ))

        if violations:
            return ContractResult(
                passed=False,
                violations=violations,
                message=f"发现 {len(violations)} 个契约违规",
            )

        return ContractResult(passed=True, message="契约验证通过")

    def _validate_body(
        self,
        actual: Any,
        contract: Dict[str, Any],
        path: str,
    ) -> List[ContractViolation]:
        """
        递归验证响应体字段。

        Args:
            actual: 实际响应体。
            contract: 响应体契约定义。
            path: 当前字段路径。

        Returns:
            违规记录列表。
        """
        violations: List[ContractViolation] = []

        # 检查必需字段
        required_fields = contract.get("required_fields", [])
        if isinstance(actual, dict):
            for fld in required_fields:
                if fld not in actual:
                    violations.append(ContractViolation(
                        field_path=f"{path}.{fld}",
                        expected="字段存在",
                        actual="字段缺失",
                        violation_type="missing_field",
                        message=f"缺少必需字段: {path}.{fld}",
                    ))

        # 检查属性类型
        properties = contract.get("properties", {})
        if isinstance(actual, dict):
            for prop_name, prop_schema in properties.items():
                if prop_name in actual:
                    expected_type = prop_schema.get("type", "")
                    actual_value = actual[prop_name]
                    if not self._check_type(actual_value, expected_type):
                        violations.append(ContractViolation(
                            field_path=f"{path}.{prop_name}",
                            expected=expected_type,
                            actual=type(actual_value).__name__,
                            violation_type="type_mismatch",
                            message=f"字段类型不匹配 {path}.{prop_name}: 期望 {expected_type}，实际 {type(actual_value).__name__}",
                        ))

        return violations

    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """
        检查值是否符合期望类型。

        Args:
            value: 待检查的值。
            expected_type: 期望的类型字符串。

        Returns:
            类型是否匹配。
        """
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # 未知类型不做检查
        return isinstance(value, expected)
