"""
执行上下文模型 — 封装测试运行时的全局共享状态。

ExecutionContext 在整个测试计划执行期间传递，
包含计划、目标系统、配置、环境信息和运行时变量。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict

from .target_system import TargetSystem
from .test_plan import TestPlan


@dataclass
class EnvironmentInfo:
    """
    运行环境信息。

    Attributes:
        os: 操作系统名称（如 'Linux', 'Windows'）。
        python_version: Python 版本号。
        node_version: Node.js 版本号（可选）。
        shell: Shell 类型（如 'bash', 'powershell'）。
        env_vars: 相关环境变量。
        is_ci: 是否在 CI 环境中运行。
    """

    os: str = ""
    python_version: str = ""
    node_version: str = ""
    shell: str = ""
    env_vars: Dict[str, str] = field(default_factory=dict)
    is_ci: bool = False


@dataclass
class ExecutionContext:
    """
    执行上下文 — 测试运行时的全局共享状态容器。

    在引擎 run() 方法中创建并传递给各阶段，
    支持在套件/用例间共享运行时变量。

    Attributes:
        plan: 当前执行的测试计划。
        target: 被测目标系统。
        config: 当前生效的完整配置字典。
        env: 运行环境信息。
        start_time: 测试计划开始执行的时间。
        variables: 运行时共享变量字典，各阶段可读写。
    """

    plan: TestPlan
    target: TargetSystem
    config: Dict[str, Any] = field(default_factory=dict)
    env: EnvironmentInfo = field(default_factory=EnvironmentInfo)
    start_time: datetime = field(default_factory=datetime.now)
    variables: Dict[str, Any] = field(default_factory=dict)

    def set_variable(self, key: str, value: Any) -> None:
        """
        设置运行时共享变量。

        Args:
            key: 变量名。
            value: 变量值。
        """
        self.variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """
        获取运行时共享变量。

        Args:
            key: 变量名。
            default: 变量不存在时的默认值。

        Returns:
            变量值。
        """
        return self.variables.get(key, default)

    @property
    def elapsed_seconds(self) -> float:
        """获取从开始执行到现在的耗时（秒）。"""
        return (datetime.now() - self.start_time).total_seconds()
