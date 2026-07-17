"""
子进程运行器 — 封装子进程运行细节。

职责：处理超时控制、输出捕获、退出码解析，
      提供 run() / run_python() / run_with_streaming() 三种运行方式。
"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import Any, Callable, Dict, List, Optional

from ..bridge import ExecutionResult

logger = logging.getLogger(__name__)


class SubprocessRunner:
    """
    子进程运行器 — 封装 asyncio.create_subprocess_exec 的调用细节。

    提供统一的子进程执行接口，自动处理：
    - 超时终止
    - stdout/stderr 捕获
    - 退出码解析
    - 流式输出回调
    """

    async def run(
        self,
        cmd: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 300,
        capture: bool = True,
        script_label: str = "",
    ) -> ExecutionResult:
        """
        运行子进程命令。

        Args:
            cmd: 命令列表（如 ['python', 'script.py', '--arg', 'value']）。
            cwd: 工作目录。
            env: 环境变量（覆盖当前环境变量）。
            timeout: 超时时间（秒）。
            capture: 是否捕获输出。
            script_label: 脚本标识（用于日志和结果记录）。

        Returns:
            统一的执行结果。
        """
        start_time = time.time()
        label = script_label or " ".join(cmd[:2])
        logger.debug(f"启动子进程: {' '.join(cmd)}")

        try:
            # 创建子进程
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE if capture else None,
                stderr=asyncio.subprocess.PIPE if capture else None,
                cwd=cwd,
                env=env,
            )

            # 等待进程完成（带超时）
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                # 超时后强制终止
                process.kill()
                await process.wait()
                duration = time.time() - start_time
                return ExecutionResult(
                    language="python",
                    script=label,
                    exit_code=-1,
                    stdout="",
                    stderr=f"子进程超时终止: {timeout}s",
                    duration=duration,
                    success=False,
                )

            # 解析输出
            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            exit_code = process.returncode or 0
            duration = time.time() - start_time

            # 尝试解析 JSON 输出
            data = self._try_parse_json(stdout)

            result = ExecutionResult(
                language="python",
                script=label,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                data=data,
                success=(exit_code == 0),
            )

            if not result.success:
                logger.warning(f"子进程退出码 {exit_code}: {label}")
            return result

        except FileNotFoundError:
            duration = time.time() - start_time
            return ExecutionResult(
                language="python",
                script=label,
                exit_code=-1,
                stdout="",
                stderr=f"命令未找到: {cmd[0]}",
                duration=duration,
                success=False,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"子进程执行异常: {e}")
            return ExecutionResult(
                language="python",
                script=label,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
                success=False,
            )

    async def run_python(
        self,
        script: str,
        args: Optional[List[str]] = None,
        timeout: float = 300,
    ) -> ExecutionResult:
        """
        运行 Python 脚本。

        Args:
            script: Python 脚本路径。
            args: 额外的命令行参数列表。
            timeout: 超时时间（秒）。

        Returns:
            执行结果。
        """
        cmd = [sys.executable, script]
        if args:
            cmd.extend(args)
        return await self.run(cmd=cmd, timeout=timeout, script_label=script)

    async def run_with_streaming(
        self,
        cmd: List[str],
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
        timeout: float = 300,
    ) -> ExecutionResult:
        """
        运行子进程并支持流式输出回调。

        Args:
            cmd: 命令列表。
            on_stdout: stdout 逐行回调函数。
            on_stderr: stderr 逐行回调函数。
            timeout: 超时时间。

        Returns:
            执行结果（包含所有输出的拼接）。
        """
        start_time = time.time()
        stdout_lines: List[str] = []
        stderr_lines: List[str] = []

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # 逐行读取 stdout
            async def read_stream(stream, callback, collector):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip("\n")
                    collector.append(text)
                    if callback:
                        callback(text)

            # 并发读取 stdout 和 stderr
            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(process.stdout, on_stdout, stdout_lines),
                    read_stream(process.stderr, on_stderr, stderr_lines),
                ),
                timeout=timeout,
            )
            await process.wait()

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()

        duration = time.time() - start_time
        exit_code = process.returncode or 0

        return ExecutionResult(
            language="python",
            script=" ".join(cmd[:2]),
            exit_code=exit_code,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
            duration=duration,
            success=(exit_code == 0),
        )

    @staticmethod
    def _try_parse_json(text: str) -> Dict[str, Any]:
        """
        尝试将 stdout 解析为 JSON，失败时返回空字典。

        Args:
            text: stdout 文本内容。

        Returns:
            解析后的字典，或空字典。
        """
        import json
        try:
            result = json.loads(text.strip())
            return result if isinstance(result, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}
