"""
Node.js 执行器 — Node.js 语言的桥接执行器。

通过子进程运行 Node 脚本，支持 JSON 序列化结果回传。
使用 bridge.js 作为 Node 端统一入口脚本。
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from typing import Any, Dict, List, Optional

from ..bridge import ExecutionResult, LanguageBridge
from .node_runner import NodeRunner

logger = logging.getLogger(__name__)


class NodeExecutor(LanguageBridge):
    """
    Node.js 语言执行器。

    通过 subprocess 运行 Node.js 脚本，
    使用 bridge.js 作为统一入口，支持 JSON 结果回传。

    Attributes:
        _node_path: Node.js 可执行文件路径。
        _modules_dir: Node 模块目录（包含 bridge.js）。
        _runner: Node 脚本运行器。
    """

    def __init__(
        self,
        node_path: str = "node",
        modules_dir: str = "nodejs_modules",
    ) -> None:
        """
        初始化 Node.js 执行器。

        Args:
            node_path: node 可执行文件路径或名称。
            modules_dir: Node.js 模块目录。
        """
        self._node_path = node_path
        self._modules_dir = modules_dir
        self._runner = NodeRunner(node_path=node_path, modules_dir=modules_dir)

    @property
    def language(self) -> str:
        """语言标识。"""
        return "nodejs"

    async def execute(
        self,
        script_or_callable: Any,
        args: Optional[Dict[str, Any]] = None,
        timeout: float = 300,
    ) -> ExecutionResult:
        """
        通过 Node.js 执行脚本。

        Args:
            script_or_callable: JS 脚本路径或内联代码。
            args: 传递给脚本的参数。
            timeout: 超时时间（秒）。

        Returns:
            统一的执行结果。
        """
        script = str(script_or_callable)

        # 判断是文件路径还是内联代码
        if os.path.isfile(script):
            return await self._runner.run_script(
                script_path=script,
                args=args,
                timeout=timeout,
            )
        else:
            return await self._runner.run_inline(
                js_code=script,
                timeout=min(timeout, 60),
            )

    async def is_available(self) -> bool:
        """检测 node 是否可在 PATH 中找到。"""
        return shutil.which(self._node_path) is not None

    def get_version(self) -> Optional[str]:
        """
        获取 Node.js 版本号。

        Returns:
            版本号字符串（如 'v20.11.0'），不可用时返回 None。
        """
        import subprocess
        try:
            result = subprocess.run(
                [self._node_path, "--version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
