"""
环境检测模块 — 检测运行环境并输出环境信息。

检测内容包括：操作系统、Python 版本、Node.js 版本、Shell 类型、
环境变量、CI 环境标识等。
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..core.models.execution_context import EnvironmentInfo


class EnvironmentDetector:
    """
    环境检测器 — 收集当前运行环境的全部信息。

    在框架启动阶段由 Bootstrapper 调用，
    检测结果存储到 EnvironmentInfo 供后续模块使用。
    """

    def detect(self) -> EnvironmentInfo:
        """
        执行完整的环境检测。

        Returns:
            包含操作系统、语言版本、环境变量的 EnvironmentInfo 实例。
        """
        return EnvironmentInfo(
            os=platform.system(),
            python_version=self._get_python_version(),
            node_version=self._get_node_version(),
            shell=self._detect_shell(),
            env_vars=self._collect_env_vars(),
            is_ci=self._detect_ci(),
        )

    def validate(self, info: EnvironmentInfo) -> List[str]:
        """
        验证环境是否满足框架运行要求。

        Args:
            info: 环境信息实例。

        Returns:
            警告消息列表，空列表表示环境完全满足要求。
        """
        warnings = []

        # 检查 Python 版本 >= 3.10
        major, minor = info.python_version.split(".")[:2]
        if int(major) < 3 or (int(major) == 3 and int(minor) < 10):
            warnings.append(f"Python 版本 {info.python_version} 低于最低要求 3.10")

        return warnings

    def _get_python_version(self) -> str:
        """获取 Python 版本号。"""
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _get_node_version(self) -> str:
        """获取 Node.js 版本号，未安装返回空字符串。"""
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip().lstrip("v") if result.returncode == 0 else ""
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    def _detect_shell(self) -> str:
        """检测当前 Shell 类型。"""
        if platform.system() == "Windows":
            return "powershell"
        return os.environ.get("SHELL", "bash").split("/")[-1]

    def _collect_env_vars(self) -> Dict[str, str]:
        """收集框架相关环境变量（TF_ 前缀）。"""
        return {
            key: value
            for key, value in os.environ.items()
            if key.startswith("TF_")
        }

    def _detect_ci(self) -> bool:
        """检测是否在 CI 环境中运行。"""
        ci_indicators = ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "TRAVIS"]
        return any(os.environ.get(var) for var in ci_indicators)
