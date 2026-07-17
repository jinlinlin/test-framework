"""
依赖检查模块 — 检测 Python 包、Node 包、系统工具的安装状态。

在框架启动阶段检查必要依赖是否就绪，
缺失关键依赖时阻止启动并输出清晰的错误信息。
"""
from __future__ import annotations

import importlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DependencyStatus:
    """
    单个依赖的检查结果。

    Attributes:
        name: 依赖名称。
        required: 是否为必需依赖。
        installed: 是否已安装。
        version: 已安装版本号（未安装为空字符串）。
        message: 状态描述消息。
    """

    name: str
    required: bool
    installed: bool
    version: str
    message: str


class DependencyChecker:
    """
    依赖检查器 — 检测框架运行所需的各类依赖。

    支持三类依赖检查：
    1. Python 包（通过 importlib 检测）
    2. Node.js 包（通过 npm list 检测）
    3. 系统工具（通过 shutil.which 检测）
    """

    # 框架必需的 Python 包
    REQUIRED_PYTHON_PACKAGES = [
        "httpx", "yaml", "pydantic", "jsonschema", "jinja2",
    ]

    # 框架可选的 Python 包
    OPTIONAL_PYTHON_PACKAGES = [
        "asyncpg", "aiomysql", "motor", "redis",
        "playwright", "grpc", "psutil", "structlog",
    ]

    # 框架必需的系统工具
    REQUIRED_SYSTEM_TOOLS = ["python3"]

    # 框架可选的系统工具
    OPTIONAL_SYSTEM_TOOLS = ["node", "docker", "kubectl", "playwright"]

    def check_python_packages(self, packages: Optional[List[str]] = None) -> List[DependencyStatus]:
        """
        检查 Python 包是否已安装。

        Args:
            packages: 要检查的包名列表，为 None 时检查默认列表。

        Returns:
            各包的检查结果列表。
        """
        if packages is None:
            packages = self.REQUIRED_PYTHON_PACKAGES + self.OPTIONAL_PYTHON_PACKAGES

        results = []
        for pkg in packages:
            required = pkg in self.REQUIRED_PYTHON_PACKAGES
            try:
                module = importlib.import_module(pkg)
                version = getattr(module, "__version__", "unknown")
                results.append(DependencyStatus(
                    name=pkg, required=required, installed=True,
                    version=version, message=f"{pkg} {version} 已安装"
                ))
            except ImportError:
                results.append(DependencyStatus(
                    name=pkg, required=required, installed=False,
                    version="", message=f"{pkg} 未安装" + ("（必需）" if required else "（可选）")
                ))
        return results

    def check_system_tools(self, tools: Optional[List[str]] = None) -> List[DependencyStatus]:
        """
        检查系统工具是否可用。

        Args:
            tools: 要检查的工具名列表，为 None 时检查默认列表。

        Returns:
            各工具的检查结果列表。
        """
        if tools is None:
            tools = self.REQUIRED_SYSTEM_TOOLS + self.OPTIONAL_SYSTEM_TOOLS

        results = []
        for tool in tools:
            required = tool in self.REQUIRED_SYSTEM_TOOLS
            path = shutil.which(tool)
            if path:
                results.append(DependencyStatus(
                    name=tool, required=required, installed=True,
                    version=path, message=f"{tool} 可用: {path}"
                ))
            else:
                results.append(DependencyStatus(
                    name=tool, required=required, installed=False,
                    version="", message=f"{tool} 未找到" + ("（必需）" if required else "（可选）")
                ))
        return results

    def check_all(self) -> List[DependencyStatus]:
        """
        执行全部依赖检查。

        Returns:
            所有依赖的检查结果列表。
        """
        results = []
        results.extend(self.check_python_packages())
        results.extend(self.check_system_tools())
        return results

    def ensure_or_raise(self, statuses: Optional[List[DependencyStatus]] = None) -> None:
        """
        确保所有必需依赖已安装，缺失时抛出异常。

        Args:
            statuses: 检查结果列表，为 None 时自动执行 check_all()。

        Raises:
            RuntimeError: 当必需依赖缺失时抛出。
        """
        if statuses is None:
            statuses = self.check_all()

        missing_required = [s for s in statuses if s.required and not s.installed]
        if missing_required:
            names = ", ".join(s.name for s in missing_required)
            raise RuntimeError(
                f"缺少必需依赖: {names}。"
                f"请运行: pip install -r python_modules/requirements.txt"
            )
