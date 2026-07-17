"""
Python 执行器 — Python 语言的桥接执行器。

支持两种执行模式：
  - native：同进程直接调用 Python 函数/类（低延迟）
  - subprocess：通过子进程运行独立 Python 脚本（隔离性高）
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any, Callable, Dict, List, Optional

from ..bridge import ExecutionResult, LanguageBridge
from .native_bridge import NativeBridge
from .subprocess_runner import SubprocessRunner

logger = logging.getLogger(__name__)


class PythonExecutor(LanguageBridge):
    """
    Python 语言执行器。

    根据 mode 参数选择执行模式：
    - 'native'：在当前进程内直接调用（适合函数/类调用）
    - 'subprocess'：启动子进程运行脚本（适合独立脚本执行）

    Attributes:
        _mode: 执行模式（native / subprocess）。
        _native_bridge: 原生调用桥接器。
        _subprocess_runner: 子进程运行器。
    """

    def __init__(self, mode: str = "native") -> None:
        """
        初始化 Python 执行器。

        Args:
            mode: 执行模式，'native' 或 'subprocess'。
        """
        if mode not in ("native", "subprocess"):
            raise ValueError(f"不支持的模式: {mode!r}，可选: 'native', 'subprocess'")
        self._mode = mode
        self._native_bridge = NativeBridge()
        self._subprocess_runner = SubprocessRunner()

    @property
    def language(self) -> str:
        """语言标识。"""
        return "python"

    async def execute(
        self,
        script_or_callable: Any,
        args: Optional[Dict[str, Any]] = None,
        timeout: float = 300,
    ) -> ExecutionResult:
        """
        执行 Python 脚本或可调用对象。

        Args:
            script_or_callable: Python 脚本路径(str)或可调用对象(Callable)。
            args: 参数列表或字典。
            timeout: 超时时间（秒）。

        Returns:
            统一的执行结果。
        """
        if self._mode == "native" and callable(script_or_callable):
            return await self._execute_native(script_or_callable, args, timeout)
        else:
            return await self._execute_subprocess(str(script_or_callable), args, timeout)

    async def _execute_native(
        self,
        callable_: Callable,
        args: Optional[Dict[str, Any]],
        timeout: float,
    ) -> ExecutionResult:
        """
        同进程直接调用可调用对象。

        Args:
            callable_: 可调用对象（函数/类方法）。
            args: 参数。
            timeout: 超时时间。

        Returns:
            执行结果。
        """
        start_time = time.time()
        try:
            # 调用函数
            call_args = args or {}
            if asyncio.iscoroutinefunction(callable_):
                result = await asyncio.wait_for(callable_(**call_args), timeout=timeout)
            else:
                result = callable_(**call_args)

            duration = time.time() - start_time
            return ExecutionResult(
                language="python",
                script=callable_.__name__ if hasattr(callable_, "__name__") else str(callable_),
                exit_code=0,
                stdout=str(result) if result is not None else "",
                stderr="",
                duration=duration,
                data={"result": result} if isinstance(result, dict) else {"result": str(result)},
                success=True,
            )
        except asyncio.TimeoutError:
            duration = time.time() - start_time
            return ExecutionResult(
                language="python",
                script=str(callable_),
                exit_code=-1,
                stdout="",
                stderr=f"执行超时: {timeout}s",
                duration=duration,
                success=False,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Python 原生执行异常: {e}")
            return ExecutionResult(
                language="python",
                script=str(callable_),
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration=duration,
                success=False,
            )

    async def _execute_subprocess(
        self,
        script_path: str,
        args: Optional[Dict[str, Any]],
        timeout: float,
    ) -> ExecutionResult:
        """
        通过子进程运行独立 Python 脚本。

        Args:
            script_path: Python 脚本文件路径。
            args: 命令行参数。
            timeout: 超时时间。

        Returns:
            执行结果。
        """
        # 构建命令行参数列表
        cmd = [sys.executable, script_path]
        if args:
            for key, value in args.items():
                if not key.startswith("_"):
                    cmd.extend([f"--{key}", str(value)])

        return await self._subprocess_runner.run(
            cmd=cmd,
            timeout=timeout,
            script_label=script_path,
        )

    async def is_available(self) -> bool:
        """Python 运行环境始终可用。"""
        return True

    def get_version(self) -> str:
        """获取 Python 版本号。"""
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
