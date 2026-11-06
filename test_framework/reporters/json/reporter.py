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
from typing import Any, Dict, List, Optional

from ..base import BaseReporter

logger = logging.getLogger(__name__)


class JSONReporter(BaseReporter):
    """
    JSON 报告器。

    双通道输出：
        - 默认通道：report_{timestamp}.json（plan 级全量报告，旧行为不变）。
        - Layer 2 通道：提供 engine+run_id 时额外产出
          ``artifacts/{engine}/{run_id}/summary.json``（引擎级汇总，
          供 Layer 3 聚合器消费）。

    配置::

        JSONReporter(
            output_dir="./reports/json",
            engine="agent_behavior",   # 可选：实例级引擎标识
            run_id=None,              # 可选：实例级运行 ID
        )
    """

    @property
    def reporter_type(self) -> str:
        return "json"

    def __init__(
        self,
        output_dir: str = "./reports/json",
        engine: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        """
        Args:
            output_dir: JSON 报告输出目录。
            engine: 实例级引擎标识（回调未传 engine 时的回退值）。
            run_id: 实例级运行 ID（回调未传 run_id 时的回退值）。
        """
        self._output_dir = output_dir
        self._engine = engine
        self._run_id = run_id
        self._test_results: List[Dict[str, Any]] = []

    async def on_test_completed(self, result: Dict[str, Any]) -> None:
        """收集每个测试结果。"""
        self._test_results.append(result)

    async def on_plan_completed(
        self,
        plan_name: str,
        results: List[Dict[str, Any]],
        run_id: Optional[str] = None,
        engine: Optional[str] = None,
    ) -> str:
        """
        生成 JSON 报告。

        Args:
            plan_name: 测试计划名称。
            results: 所有测试结果。
            run_id: 运行 ID；缺省时回退实例级 self._run_id。
            engine: 引擎标识；缺省时回退实例级 self._engine。

        Returns:
            JSON 报告文件路径。
        """
        os.makedirs(self._output_dir, exist_ok=True)

        # 优先用回调透传的值，其次用构造时的实例级值
        resolved_engine = engine or self._engine
        resolved_run_id = run_id or self._run_id

        # 构建报告结构
        total = len(results)
        passed = sum(1 for r in results if r.get("status") == "passed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        errors = sum(1 for r in results if r.get("status") == "error")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        total_duration = sum(r.get("duration", 0) for r in results)

        summary = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "pass_rate": round(passed / total * 100, 2) if total > 0 else 0,
            "total_duration": round(total_duration, 3),
        }

        report = {
            "plan_name": plan_name,
            "generated_at": datetime.datetime.now().isoformat(),
            "summary": summary,
            "results": results,
        }
        # 仅在调用方提供时写入运行维度字段，旧消费方看到的结构保持不变
        if resolved_engine is not None:
            report["engine"] = resolved_engine
        if resolved_run_id is not None:
            report["run_id"] = resolved_run_id

        # 写入文件
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.json"
        filepath = os.path.join(self._output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        # Layer 2 引擎级产物：engine 与 run_id 齐备时额外产出 summary.json，
        # 路径沿用迁移方案的约定 artifacts/{engine}/{run_id}/summary.json。
        if resolved_engine and resolved_run_id:
            artifact_dir = os.path.join(
                "artifacts", resolved_engine, resolved_run_id,
            )
            os.makedirs(artifact_dir, exist_ok=True)
            engine_summary = {
                "schema_version": "1.0",
                "engine": resolved_engine,
                "run_id": resolved_run_id,
                "plan_name": plan_name,
                "status": "completed",
                "totals": summary,
                "generated_at": report["generated_at"],
                "failures": [
                    {
                        "case_id": r.get("case_id"),
                        "status": r.get("status"),
                        "message": r.get("message", ""),
                    }
                    for r in results
                    if r.get("status") in ("failed", "error")
                ],
            }
            summary_path = os.path.join(artifact_dir, "summary.json")
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(engine_summary, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"引擎级 summary 已生成: {summary_path}")

        self._test_results.clear()
        logger.info(f"JSON 报告已生成: {filepath}")
        return filepath
