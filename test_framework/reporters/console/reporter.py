"""
Console 报告器 — 彩色实时终端输出。

特点：
- 实时打印每个用例的执行结果
- 使用 ANSI 颜色代码
- 支持汇总统计表格
"""
from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List

from ..base import BaseReporter

logger = logging.getLogger(__name__)


# ANSI 颜色代码
class _Colors:
    """终端颜色代码。"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"
    MAGENTA = "\033[35m"


class ConsoleReporter(BaseReporter):
    """
    Console 报告器。

    在终端中实时输出测试结果，支持彩色显示。
    """

    @property
    def reporter_type(self) -> str:
        return "console"

    def __init__(self, use_color: bool = True, verbose: bool = False) -> None:
        """
        Args:
            use_color: 是否使用彩色输出。
            verbose: 是否输出详细信息。
        """
        self._use_color = use_color
        self._verbose = verbose
        self._test_count = 0
        self._passed = 0
        self._failed = 0
        self._errors = 0
        self._skipped = 0

    def _color(self, text: str, color: str) -> str:
        """添加颜色。"""
        if self._use_color:
            return f"{color}{text}{_Colors.RESET}"
        return text

    def _status_icon(self, status: str) -> str:
        """获取状态图标。"""
        icons = {
            "passed": self._color("✓", _Colors.GREEN),
            "failed": self._color("✗", _Colors.RED),
            "error": self._color("⚠", _Colors.YELLOW),
            "skipped": self._color("○", _Colors.GRAY),
        }
        return icons.get(status, self._color("?", _Colors.GRAY))

    async def on_test_completed(self, result: Dict[str, Any]) -> None:
        """实时打印测试结果。"""
        status = result.get("status", "unknown")
        name = result.get("test_name", "unnamed")
        duration = result.get("duration", 0)

        self._test_count += 1
        if status == "passed":
            self._passed += 1
        elif status == "failed":
            self._failed += 1
        elif status == "error":
            self._errors += 1
        elif status == "skipped":
            self._skipped += 1

        icon = self._status_icon(status)
        line = f"  {icon} {name}"
        line += self._color(f" ({duration:.3f}s)", _Colors.GRAY)

        # 失败/错误时显示错误信息
        error_msg = result.get("error_message", "")
        if error_msg:
            line += f"\n    {self._color(error_msg[:120], _Colors.RED)}"

        print(line, flush=True)

        # 详细模式下输出指标
        if self._verbose and result.get("metrics"):
            metrics = result["metrics"]
            metrics_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
            print(f"    {self._color(metrics_str, _Colors.CYAN)}", flush=True)

    async def on_plan_completed(
        self,
        plan_name: str,
        results: List[Dict[str, Any]],
    ) -> str:
        """打印汇总统计。"""
        total = len(results)
        passed = sum(1 for r in results if r.get("status") == "passed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        errors = sum(1 for r in results if r.get("status") == "error")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        total_duration = sum(r.get("duration", 0) for r in results)
        pass_rate = (passed / total * 100) if total > 0 else 0

        # 分隔线
        sep = self._color("─" * 60, _Colors.GRAY)
        print(f"\n{sep}")
        print(self._color(f"  {plan_name}", _Colors.BOLD))
        print(sep)

        # 统计行
        print(f"  总计: {total}  ", end="")
        print(self._color(f"通过: {passed}", _Colors.GREEN) + "  ", end="")
        print(self._color(f"失败: {failed}", _Colors.RED) + "  ", end="")
        print(self._color(f"错误: {errors}", _Colors.YELLOW) + "  ", end="")
        print(self._color(f"跳过: {skipped}", _Colors.GRAY))

        # 通过率和耗时
        rate_color = _Colors.GREEN if pass_rate >= 90 else (_Colors.YELLOW if pass_rate >= 70 else _Colors.RED)
        print(f"  通过率: {self._color(f'{pass_rate:.1f}%', rate_color)}  总耗时: {total_duration:.2f}s")
        print(sep)

        # 如果全部通过
        if failed == 0 and errors == 0:
            print(self._color("  全部通过!", _Colors.GREEN + _Colors.BOLD))
        else:
            print(self._color(f"  有 {failed + errors} 个用例需要关注", _Colors.RED))

        print()
        return ""  # Console 不生成文件
