"""Layer 3 跨引擎聚合 — 消费 Layer 2 summary.json 产出跨引擎总览。

三层报告分离中的最上层：Layer 1 各引擎原生产物、Layer 2 引擎级
summary.json 契约文件均只保证"单引擎单次运行"视角可回放；本模块回答
"这一轮整体质量如何"——扫描 artifacts/{engine}/{run_id}/summary.json，
校验契约后按引擎归并 totals、汇总失败清单，输出 aggregate.json。

设计约束：
- 只读消费，不修改任何 Layer 1/Layer 2 产物；聚合失败不影响源产物。
- 坏数据不静默：schema 违规、文件损坏、版本不兼容全部进 warnings，
  随聚合结果落盘，供报告消费方区分"没有数据"与"数据不可信"。
- 外部推送（IM/邮件/看板）不在本模块，统一收敛到后续 Layer 3 推送器。
"""
from __future__ import annotations

import glob
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 本层可消费的 Layer 2 契约主版本（不兼容主版本的 summary 只告警不聚合）
SUPPORTED_SCHEMA_MAJOR = "1"

# Layer 2 契约的必备字段（缺一即视为坏数据，进 warnings 不入聚合）
REQUIRED_FIELDS = ("schema_version", "engine", "run_id", "plan_name", "totals")

_SUMMARY_GLOB = os.path.join("artifacts", "*", "*", "summary.json")


def scan_summaries(
    artifacts_root: str = ".",
    engines: Optional[List[str]] = None,
    since: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """扫描并校验 Layer 2 summary.json，返回（合格条目, 告警）。

    Args:
        artifacts_root: 聚合视角的根目录（其下应有 {engine}/{run_id}/summary.json）。
        engines: 引擎白名单；None 表示全部引擎。
        since: 时间下界；summary.generated_at 早于该时刻的排除。

    Returns:
        (summaries, warnings)：summaries 为通过校验的 dict 列表；
        warnings 为 [{"path": ..., "reason": ...}]，坏数据在此显式化。
    """
    pattern = os.path.join(artifacts_root, _SUMMARY_GLOB)
    summaries: List[Dict[str, Any]] = []
    warnings: List[Dict[str, str]] = []

    for path in sorted(glob.glob(pattern)):
        engine = os.path.basename(os.path.dirname(os.path.dirname(path)))
        if engines and engine not in engines:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append({"path": path, "reason": f"读取失败: {exc}"})
            continue
        problems = _validate(data)
        if problems:
            warnings.append({"path": path, "reason": "; ".join(problems)})
            continue
        if since is not None:
            generated = _parse_ts(data.get("generated_at", ""))
            if generated is not None and generated < since:
                continue  # 时间窗过滤是正常排除，不算坏数据
        summaries.append(data)

    if warnings:
        logger.warning(f"summary 扫描发现 {len(warnings)} 条坏数据，已排除出聚合")
    return summaries, warnings


def _validate(data: Any) -> List[str]:
    """校验单条 summary 是否符合 Layer 2 契约，返回问题列表（空为合格）。"""
    problems: List[str] = []
    if not isinstance(data, dict):
        return [f"顶层不是对象（{type(data).__name__}）"]
    missing = [k for k in REQUIRED_FIELDS if k not in data]
    if missing:
        problems.append(f"缺字段: {missing}")
    version = str(data.get("schema_version", ""))
    if version and version.split(".")[0] != SUPPORTED_SCHEMA_MAJOR:
        problems.append(f"schema_version {version!r} 主版本不兼容")
    totals = data.get("totals")
    if isinstance(totals, dict):
        for key in ("total", "passed", "failed"):
            if not isinstance(totals.get(key), (int, float)):
                problems.append(f"totals.{key} 缺失或非数值")
    return problems


def _parse_ts(value: str) -> Optional[datetime]:
    """解析 ISO 时间戳；不可解析返回 None（交由调用方决定取舍）。"""
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def aggregate(
    summaries: List[Dict[str, Any]],
    warnings: Optional[List[Dict[str, str]]] = None,
    aggregate_id: Optional[str] = None,
) -> Dict[str, Any]:
    """把合格的 Layer 2 条目归并为跨引擎聚合结构（纯函数，不落盘）。

    pass_rate 按用例数加权合并后重算，绝不对各 run 的百分比取平均
    （小样本 run 与大样本 run 在平均值里权重不应相同）。

    Args:
        summaries: scan_summaries 产出的合格条目。
        warnings: 扫描期告警，原样带入聚合结构供消费方辨别数据完整性。
        aggregate_id: 外部指定的聚合 ID（编排器统一分配场景）；缺省自动生成。

    Returns:
        aggregate.json 的完整 dict。
    """
    warnings = warnings or []
    by_engine: Dict[str, Any] = {}
    failures: List[Dict[str, Any]] = []
    timestamps: List[datetime] = []

    for s in summaries:
        engine = s["engine"]
        grp = by_engine.setdefault(engine, {
            "runs": [], "total": 0, "passed": 0, "failed": 0,
            "errors": 0, "skipped": 0, "pass_rate": 0.0,
        })
        t = s["totals"]
        grp["runs"].append({
            "run_id": s["run_id"],
            "plan_name": s.get("plan_name", ""),
            "generated_at": s.get("generated_at", ""),
        })
        for key in ("total", "passed", "failed", "errors", "skipped"):
            grp[key] += int(t.get(key, 0) or 0)
        for f in s.get("failures", []):
            failures.append({"engine": engine, "run_id": s["run_id"], **f})
        parsed = _parse_ts(s.get("generated_at", ""))
        if parsed:
            timestamps.append(parsed)

    overall = {"engines": len(by_engine), "runs": len(summaries)}
    for key in ("total", "passed", "failed", "errors", "skipped"):
        overall[key] = sum(g[key] for g in by_engine.values())
    overall["pass_rate"] = _rate(overall["passed"], overall["total"])
    for grp in by_engine.values():
        grp["pass_rate"] = _rate(grp["passed"], grp["total"])

    return {
        "schema_version": "1.0",
        "aggregate_id": aggregate_id or _new_aggregate_id(),
        "generated_at": datetime.now().isoformat(),
        "window": {
            "from": min(timestamps).isoformat() if timestamps else None,
            "to": max(timestamps).isoformat() if timestamps else None,
        },
        "sources": {
            "scanned_included": len(summaries),
            "warnings": len(warnings),
            "warning_detail": warnings,
        },
        "overall": overall,
        "by_engine": by_engine,
        "failures": failures,
    }


def _rate(part: int, whole: int) -> float:
    """百分比通过率，零样本返回 0.0（不是除零也不是 100）。"""
    return round(part / whole * 100, 2) if whole else 0.0


def _new_aggregate_id() -> str:
    """聚合 ID：时间戳 + 短随机段，与引擎 run_id 生成风格一致。"""
    return f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def write_aggregate(
    agg: Dict[str, Any], out_root: str = os.path.join("artifacts", "aggregate")
) -> str:
    """聚合结果落盘 artifacts/aggregate/{aggregate_id}/aggregate.json。

    Returns:
        aggregate.json 路径。
    """
    target_dir = os.path.join(out_root, agg["aggregate_id"])
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, "aggregate.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False, indent=2, default=str)
    logger.info(f"Layer 3 聚合报告已生成: {path}")
    return path


def render_console(agg: Dict[str, Any]) -> str:
    """渲染控制台总览文本（首版 Dashboard 的最低成本形态）。"""
    o = agg["overall"]
    lines = [
        f"跨引擎聚合 {agg['aggregate_id']}  "
        f"[{agg['window']['from'] or '-'} ~ {agg['window']['to'] or '-'}]",
        f"整体: {o['passed']}/{o['total']} 通过（{o['pass_rate']}%），"
        f"失败 {o['failed']} 错误 {o['errors']} 跳过 {o['skipped']}，"
        f"引擎 {o['engines']} 个 / run {o['runs']} 次",
    ]
    for engine, g in sorted(agg["by_engine"].items()):
        lines.append(
            f"  {engine:24} runs={len(g['runs']):2} "
            f"passed={g['passed']}/{g['total']:<4} rate={g['pass_rate']:6.2f}%"
        )
    warn = agg["sources"]["warnings"]
    if warn:
        lines.append(f"  ⚠ 坏数据 {warn} 条（详见 sources.warning_detail）")
    if agg["failures"]:
        lines.append(f"  失败清单 {len(agg['failures'])} 条（详见 failures）")
    return "\n".join(lines)
