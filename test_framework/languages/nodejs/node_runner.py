"""
Node 脚本运行器 — 封装 Node.js 进程启动和参数传递。

职责：构建 node 命令行、处理 JSON 参数传递、
      捕获输出并解析 JSON 结果。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from ..bridge import ExecutionResult

logger = logging.getLogger(__name__)


class NodeRunner:
    """
    Node 脚本运行器。

    封装 node 进程的启动、参数构建和输出解析。

    Attributes:
        _node_path: node 可执行文件路径。
        _modules_dir: Node.js 模块目录（包含 bridge.js）。
    """

    def __init__(self, node_path: str, modules_dir: str) -> None:
        """
        初始化 Node 运行器。

        Args:
            node_path: node 可执行文件路径。
            modules_dir: 模块目录路径。
        """
        self._node_path = node_path
        self._modules_dir = modules_dir

    async def run_script(
        self,
        script_path: str,
        args: Optional[Dict[str, Any]] = None,
        timeout: float = 300,
    ) -> ExecutionResult:
        """
        运行 Node.js 脚本文件。

        Args:
            script_path: JS 脚本文件路径。
            args: 传递给脚本的参数字典（将序列化为 JSON）。
            timeout: 超时时间（秒）。

        Returns:
            执行结果。
        """
        cmd = self._build_command(script_path, args)
        return await self._execute(cmd, timeout=timeout, label=script_path)

    async def run_inline(
        self,
        js_code: str,
        timeout: float = 60,
    ) -> ExecutionResult:
        """
        运行内联 JavaScript 代码。

        Args:
            js_code: JavaScript 代码字符串。
            timeout: 超时时间（秒）。

        Returns:
            执行结果。
        """
        cmd = [self._node_path, "-e", js_code]
        return await self._execute(cmd, timeout=timeout, label="<inline>")

    def _build_command(
        self,
        script: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        构建 node 命令行参数。

        如果 bridge.js 存在，通过 bridge.js 入口执行；
        否则直接运行脚本。

        Args:
            script: 脚本路径。
            args: 参数。

        Returns:
            命令行参数列表。
        """
        bridge_path = os.path.join(self._modules_dir, "bridge.js")

        if os.path.exists(bridge_path):
            # 通过 bridge.js 入口执行
            cmd = [
                self._node_path,
                bridge_path,
                f"--module={script}",
            ]
            if args:
                args_json = json.dumps(args, ensure_ascii=False)
                cmd.append(f"--args={args_json}")
        else:
            # 直接运行脚本
            cmd = [self._node_path, script]
            if args:
                for key, value in args.items():
                    if not key.startswith("_"):
                        cmd.extend([f"--{key}", str(value)])

        return cmd

    async def _execute(
        self,
        cmd: List[str],
        timeout: float,
        label: str,
    ) -> ExecutionResult:
        """
        执行 node 子进程命令。

        Args:
            cmd: 命令行参数列表。
            timeout: 超时时间。
            label: 脚本标识（用于日志）。

        Returns:
            执行结果。
        """
        start_time = time.time()
        logger.debug(f"启动 Node 进程: {' '.join(cmd)}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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
                    language="nodejs",
                    script=label,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Node 进程超时终止: {timeout}s",
                    duration=duration,
                    success=False,
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            exit_code = process.returncode or 0
            duration = time.time() - start_time

            # 尝试解析 JSON 结果
            data = self._parse_json_output(stdout)

            return ExecutionResult(
                language="nodejs",
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
                language="nodejs",
                script=label,
                exit_code=-1,
                stdout="",
                stderr=f"Node 未找到: {self._node_path}",
                duration=duration,
                success=False,
            )
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Node 执行异常: {e}")
            return ExecutionResult(
                language="nodejs",
                script=label,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
                success=False,
            )

    @staticmethod
    def _parse_json_output(stdout: str) -> Dict[str, Any]:
        """
        尝试从 stdout 解析 JSON 数据。

        Args:
            stdout: 标准输出文本。

        Returns:
            解析后的字典，或空字典。
        """
        try:
            # 查找最后一行 JSON 输出
            lines = stdout.strip().split("\n")
            for line in reversed(lines):
                line = line.strip()
                if line.startswith("{"):
                    result = json.loads(line)
                    return result if isinstance(result, dict) else {}
        except (json.JSONDecodeError, ValueError):
            pass
        return {}
