"""
Layer 2 产物写出 — 引擎级 summary.json。

职责：把 TestResult 列表转成 JSONReporter 的结果字典格式，
      经其 Layer 2 通道产出 artifacts/{engine}/{run_id}/summary.json。

为什么复用 JSONReporter 而不是在本模块直接写文件：
    summary.json 的 schema（schema_version/totals/failures 等）由
    报告层单点定义与维护；引擎侧另写一份会造成双出口，
    schema 演进时必然漂移。本模块仅做薄封装。
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List

from ...core.models import TestResult
from ...reporters.json.reporter import JSONReporter

logger = logging.getLogger(__name__)

# summary.json 相对 CWD 的落盘路径模板（与 JSONReporter Layer 2 通道一致）
_SUMMARY_PATH_TEMPLATE = os.path.join("artifacts", "{engine}", "{run_id}", "summary.json")


def summary_path(engine: str, run_id: str) -> str:
    """
    计算 Layer 2 产物的预期路径（不保证文件已存在）。

    Args:
        engine: 引擎标识（TestType 枚举值）。
        run_id: 运行 ID。

    Returns:
        summary.json 相对路径。
    """
    return _SUMMARY_PATH_TEMPLATE.format(engine=engine, run_id=run_id)


async def write_engine_summary(
    plan_name: str,
    results: List[TestResult],
    run_id: str,
    engine: str,
    output_dir: str = "./reports/json",
) -> Dict[str, str]:
    """
    产出 plan 级 JSON 报告与 Layer 2 summary.json。

    Args:
        plan_name: 测试计划名称。
        results: 引擎收口后的测试结果列表。
        run_id: 运行 ID（Layer 2 路径维度）。
        engine: 引擎标识（Layer 2 路径维度）。
        output_dir: plan 级 JSON 报告目录（Layer 1 全量报告）。

    Returns:
        {"report_path": plan 级报告路径, "summary_path": Layer 2 产物路径}。
    """
    reporter = JSONReporter(output_dir=output_dir, engine=engine, run_id=run_id)
    result_dicts = [r.to_dict() for r in results]
    report_path = await reporter.on_plan_completed(
        plan_name, result_dicts, run_id=run_id, engine=engine,
    )
    return {"report_path": report_path, "summary_path": summary_path(engine, run_id)}
