"""
Shell 脚本运行器 — 处理脚本执行、环境变量注入、输出解析。

职责：封装 Shell 脚本和命令的执行细节，
      支持脚本文件运行、内联命令运行和环境变量注入。
"""
from __future__ import annotations

import asyncio
import logging
import os
import platform
import time
from typing import Any, Dict, List, Optional

from ..bridge import ExecutionResult

logger = logging.getLogger(__name__)


class ShellRunner:
    """
    Shell 脚本运行器。

    封装不同 Shell 的命令执行细节，提供统一的运行接口。

    Attributes:
        _shell: Shell 可执行文件路径。
    """

    def __init__(self, shell: str) -> None:
        """
        初始化 Shell 运行器。

        Args:
            shell: Shell 可执行文件路径。
        """
        self._shell = shell

    async def run_script(
        self,
        script_path: str,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 300,
    ) -> ExecutionResult:
        """
        运行 Shell 脚本文件。

        Args:
            script_path: 脚本文件路径。
            env: 额外的环境变量。
            timeout: 超时时间（秒）。

        Returns:
            执行结果。
        """
        # 构建环境变量
        run_env = os.environ.copy()
        if env:
            run_env.update({k: str(v) for k, v in env.items() if not k.startswith("_")})

        # 构建命令
        if platform.system() == "Windows":
            cmd = [self._shell, "-ExecutionPolicy", "Bypass", "-File", script_path]
        else:
            cmd = [self._shell, script_path]

        return await self._execute(
            cmd=cmd,
            env=run_env,
            timeout=timeout,
            label=script_path,
        )

    async def run_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: float = 60,
    ) -> ExecutionResult:
        """
        运行 Shell 内联命令。

        Args:
            command: 命令字符串。
            cwd: 工作目录。
            timeout: 超时时间（秒）。

        Returns:
            执行结果。
        """
        # 根据 Shell 类型构建命令
        if platform.system() == "Windows" and "powershell" in self._shell.lower():
            cmd = [self._shell, "-Command", command]
        else:
            cmd = [self._shell, "-c", command]

        return await self._execute(
            cmd=cmd,
            cwd=cwd,
            timeout=timeout,
            label=command[:50],
        )

    async def _execute(
        self,
        cmd: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: float = 300,
        label: str = "",
    ) -> ExecutionResult:
        """
        执行 Shell 子进程命令。

        Args:
            cmd: 命令行参数列表。
            env: 环境变量。
            cwd: 工作目录。
            timeout: 超时时间。
            label: 脚本标识（用于日志）。

        Returns:
            执行结果。
        """
        start_time = time.time()
        logger.debug(f"启动 Shell 进程: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                duration = time.time() - start_time
                return ExecutionResult(
                    language="shell",
                    script=label,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Shell 进程超时终止: {timeout}s",
                    duration=duration,
                    success=False,
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            exit_code = process.returncode or 0
            duration = time.time() - start_time

            # 尝试解析 JSON 输出
            data = self._try_parse_json(stdout)

            return ExecutionResult(
                language="shell",
                script=label,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                data=data,
                success=(exit_code == 0),
            )

        except FileNotFoundError:
            duration = time.time() - start_time
            return ExecutionResult(
                language="shell",
                script=label,
                exit_code=-1,
                stdout="",
                stderr=f"Shell 未找到: {self._shell}",
                duration=duration,
                success=False,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Shell 执行异常: {e}")
            return ExecutionResult(
                language="shell",
                script=label,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
                success=False,
            )

    @staticmethod
    def _try_parse_json(text: str) -> Dict[str, Any]:
        """
        尝试将 stdout 最后一行解析为 JSON。

        Args:
            text: stdout 文本。

        Returns:
            解析后的字典，或空字典。
        """
        import json
        lines = text.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line.startswith("{"):
                try:
                    result = json.loads(line)
                    return result if isinstance(result, dict) else {}
                except json.JSONDecodeError:
                    continue
        return {}
