"""
Shell 执行器 — Shell 语言的桥接执行器。

运行 Bash / Zsh / PowerShell 脚本，
自动适配 Windows（PowerShell）和 Linux（Bash）。
"""
from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
import subprocess
import time
from typing import Any, Dict, Optional

from ..bridge import ExecutionResult, LanguageBridge
from .shell_runner import ShellRunner

logger = logging.getLogger(__name__)


class ShellExecutor(LanguageBridge):
    """
    Shell 语言执行器。

    自动检测当前操作系统的默认 Shell：
    - Linux/Mac: /bin/bash
    - Windows: powershell.exe

    Attributes:
        _shell: Shell 可执行文件路径。
        _runner: Shell 脚本运行器。
    """

    def __init__(self, shell: Optional[str] = None) -> None:
        """
        初始化 Shell 执行器。

        Args:
            shell: 指定 Shell 路径，为 None 时自动检测。
        """
        self._shell = shell or self._detect_shell()
        self._runner = ShellRunner(shell=self._shell)

    @property
    def language(self) -> str:
        """语言标识。"""
        return "shell"

    async def execute(
        self,
        script_or_callable: Any,
        args: Optional[Dict[str, Any]] = None,
        timeout: float = 300,
    ) -> ExecutionResult:
        """
        执行 Shell 脚本或命令。

        Args:
            script_or_callable: Shell 脚本路径或命令字符串。
            args: 环境变量或参数。
            timeout: 超时时间（秒）。

        Returns:
            统一的执行结果。
        """
        script = str(script_or_callable)

        # 判断是脚本文件还是内联命令
        if os.path.isfile(script):
            return await self._runner.run_script(
                script_path=script,
                env=args,
                timeout=timeout,
            )
        else:
            return await self._runner.run_command(
                command=script,
                timeout=timeout,
            )

    async def is_available(self) -> bool:
        """Shell 运行环境始终可用（系统自带）。"""
        return True

    def get_version(self) -> Optional[str]:
        """
        获取 Shell 版本号。

        Returns:
            版本号字符串，无法获取时返回 None。
        """
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    [self._shell, "-Command", "$PSVersionTable.PSVersion.ToString()"],
                    capture_output=True, text=True, timeout=5,
                )
            else:
                result = subprocess.run(
                    [self._shell, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
            return result.stdout.strip() if result.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    @staticmethod
    def _detect_shell() -> str:
        """
        检测当前操作系统的默认 Shell。

        Returns:
            Shell 可执行文件路径。
        """
        system = platform.system()

        if system == "Windows":
            # Windows 优先使用 PowerShell
            ps_path = shutil.which("pwsh") or shutil.which("powershell")
            return ps_path or "powershell.exe"
        else:
            # Linux/Mac 优先使用 bash
            bash_path = shutil.which("bash")
            if bash_path:
                return bash_path
            # 回退到 sh
            sh_path = shutil.which("sh")
            return sh_path or "/bin/sh"
