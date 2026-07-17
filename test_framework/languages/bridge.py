"""
多语言桥接层 — 桥接器基类（桥接模式）。

设计模式：桥接模式 — 抽象部分与实现部分分离
职责：定义多语言桥接的统一接口，所有语言桥接器必须继承此类。
      支持 Python / Node.js / Shell 三种语言的统一执行和结果回传。
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """
    跨语言执行的统一结果模型。

    无论通过哪种语言执行脚本/函数，结果都统一封装为此对象，
    便于上层聚合、日志记录和报告生成。

    Attributes:
        language: 执行语言（python / nodejs / shell）。
        script: 执行的脚本路径或调用标识。
        exit_code: 进程退出码（0 为成功）。
        stdout: 标准输出内容。
        stderr: 标准错误内容。
        duration: 执行耗时（秒）。
        data: 结构化数据（如 JSON 解析后的结果）。
        success: 是否执行成功。
        timestamp: 执行时间戳。
    """

    language: str
    script: str
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    data: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，便于 JSON 序列化。"""
        return {
            "language": self.language,
            "script": self.script,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration": self.duration,
            "data": self.data,
            "success": self.success,
            "timestamp": self.timestamp,
        }


class LanguageBridge(ABC):
    """
    语言桥接器抽象基类。

    定义多语言执行的统一接口，所有具体语言的桥接器
    （PythonExecutor / NodeExecutor / ShellExecutor）必须继承并实现。

    设计模式：桥接模式（Bridge）
    将"执行什么"与"如何执行"解耦，上层无需关心具体语言的实现细节。
    """

    @property
    @abstractmethod
    def language(self) -> str:
        """
        返回语言标识名称。

        Returns:
            语言标识（如 'python'、'nodejs'、'shell'）。
        """
        ...

    @abstractmethod
    async def execute(
        self,
        script_or_callable: Any,
        args: Optional[Dict[str, Any]] = None,
        timeout: float = 300,
    ) -> ExecutionResult:
        """
        执行脚本或可调用对象。

        Args:
            script_or_callable: 脚本路径、代码字符串或可调用对象。
            args: 传递给脚本/函数的参数字典。
            timeout: 超时时间（秒）。

        Returns:
            统一的执行结果。
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """
        检测该语言的运行环境是否可用。

        Returns:
            True 表示环境就绪，False 表示不可用。
        """
        ...

    @abstractmethod
    def get_version(self) -> Optional[str]:
        """
        获取语言运行时的版本号。

        Returns:
            版本号字符串，无法获取时返回 None。
        """
        ...

    async def execute_with_context(
        self,
        script_or_callable: Any,
        context: Dict[str, Any],
        **kwargs: Any,
    ) -> ExecutionResult:
        """
        携带执行上下文的调用，自动注入配置和目标信息。

        将 context 中的配置信息合并到 args 中，然后调用 execute()。

        Args:
            script_or_callable: 脚本路径或可调用对象。
            context: 执行上下文（包含配置、目标系统信息等）。
            **kwargs: 额外参数传递给 execute()。

        Returns:
            统一的执行结果。
        """
        # 从上下文中提取配置和目标信息作为参数
        args = kwargs.pop("args", {}) or {}
        args["_context"] = {
            "config": context.get("config", {}),
            "target": context.get("target", {}),
            "execution_id": context.get("execution_id", ""),
        }
        return await self.execute(script_or_callable, args=args, **kwargs)
