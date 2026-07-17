"""
JSON 报告器 — 将测试结果序列化为 JSON 文件。

特点：
- 结构化输出，便于程序解析
- 支持自定义序列化
- 可被 CI/CD 管道直接消费
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Any, Dict, List

from ..base import BaseReporter

logger = logging.getLogger(__name__)


class JSONReporter(BaseReporter):
    """
    JSON 报告器。

    配置::

        JSONReporter(output_dir="./reports/json")
    """

    @property
    def reporter_type(self) -> str:
        return "json"

    def __init__(self, output_dir: str = "./reports/json") -> None:
        """
        Args:
            output_dir: JSON 报告输出目录。
        """
        self._output_dir = output_dir
        self._test_results: List[Dict[str, Any]] = []

    async def on_test_completed(self, result: Dict[str, Any]) -> None:
        """收集每个测试结果。"""
        self._test_results.append(result)

    async def on_plan_completed(
        self,
        plan_name: str,
        results: List[Dict[str, Any]],
    ) -> str:
        """
        生成 JSON 报告。

        Args:
            plan_name: 测试计划名称。
            results: 所有测试结果。

        Returns:
            JSON 报告文件路径。
        """
        os.makedirs(self._output_dir, exist_ok=True)

        # 构建报告结构
        total = len(results)
        passed = sum(1 for r in results if r.get("status") == "passed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        errors = sum(1 for r in results if r.get("status") == "error")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        total_duration = sum(r.get("duration", 0) for r in results)

        report = {
            "plan_name": plan_name,
            "generated_at": datetime.datetime.now().isoformat(),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
                "pass_rate": round(passed / total * 100, 2) if total > 0 else 0,
                "total_duration": round(total_duration, 3),
            },
            "results": results,
        }

        # 写入文件
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.json"
        filepath = os.path.join(self._output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        self._test_results.clear()
        logger.info(f"JSON 报告已生成: {filepath}")
        return filepath
