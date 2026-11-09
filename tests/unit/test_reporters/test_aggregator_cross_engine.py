"""Layer 3 跨引擎聚合器单测。

覆盖：扫描校验（坏数据显式化）、过滤（引擎白名单/时间窗）、
聚合数学（加权通过率、失败归因）、落盘与控制台渲染。
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

from test_framework.reporters.aggregator import (
    aggregate,
    render_console,
    scan_summaries,
    write_aggregate,
)


def _mk_summary(engine="agent_behavior", run_id="r1", total=4, passed=3,
                failed=1, errors=0, skipped=0, generated_at="2026-11-09T10:00:00",
                failures=None, schema_version="1.0", plan_name="回归"):
    """构造符合 Layer 2 契约 1.0 的 summary 字典（字段可逐项破坏）。"""
    data = {
        "schema_version": schema_version,
        "engine": engine,
        "run_id": run_id,
        "plan_name": plan_name,
        "status": "completed",
        "totals": {
            "total": total, "passed": passed, "failed": failed,
            "errors": errors, "skipped": skipped,
            "pass_rate": 75.0, "total_duration": 1.0,
        },
        "generated_at": generated_at,
        "failures": failures if failures is not None else [
            {"case_id": "c1", "status": "fail", "message": "断言失败"},
        ],
    }
    return data


def _put(root, data, engine=None, run_id=None):
    """把 summary 写入 root/artifacts/{engine}/{run_id}/summary.json。

    dict 数据从自身取目录维度；字符串（构造坏数据）须显式传入。
    """
    if isinstance(data, dict):
        engine = engine or data["engine"]
        run_id = run_id or data["run_id"]
    path = os.path.join(str(root), "artifacts", engine, run_id)
    os.makedirs(path, exist_ok=True)
    file = os.path.join(path, "summary.json")
    if isinstance(data, dict):
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    else:  # 原文写入（构造损坏文件）
        with open(file, "w", encoding="utf-8") as f:
            f.write(data)
    return file


class TestScan:
    """扫描与校验：合格进聚合、坏数据进 warnings，两不混淆。"""

    def test_multi_engine_all_valid(self, tmp_path):
        _put(tmp_path, _mk_summary())
        _put(tmp_path, _mk_summary(engine="rest_api", run_id="r9", failures=[]))
        summaries, warnings = scan_summaries(str(tmp_path))
        assert len(summaries) == 2 and warnings == []

    def test_broken_json_warns_not_silent(self, tmp_path):
        _put(tmp_path, _mk_summary())
        bad = _put(tmp_path, "{ not json", engine="agent_behavior", run_id="r_broken")
        summaries, warnings = scan_summaries(str(tmp_path))
        assert len(summaries) == 1
        assert len(warnings) == 1 and bad in warnings[0]["path"]
        assert "读取失败" in warnings[0]["reason"]

    def test_schema_violations_warn(self, tmp_path):
        _put(tmp_path, _mk_summary(run_id="r_v2", schema_version="2.0"))
        _put(tmp_path, _mk_summary(run_id="r_nototals", failures=[]))
        data = _mk_summary(run_id="r_missing")
        del data["totals"]
        _put(tmp_path, data)
        # r_v2: 主版本不兼容；r_missing: 缺 totals；r_nototals 合格
        summaries, warnings = scan_summaries(str(tmp_path))
        assert [s["run_id"] for s in summaries] == ["r_nototals"]
        reasons = " ".join(w["reason"] for w in warnings)
        assert "主版本不兼容" in reasons and "缺字段" in reasons

    def test_engine_filter(self, tmp_path):
        _put(tmp_path, _mk_summary())
        _put(tmp_path, _mk_summary(engine="rest_api", run_id="r2"))
        summaries, _ = scan_summaries(str(tmp_path), engines=["rest_api"])
        assert len(summaries) == 1 and summaries[0]["engine"] == "rest_api"

    def test_since_window_excludes_without_warning(self, tmp_path):
        _put(tmp_path, _mk_summary(generated_at="2026-01-01T00:00:00"))
        _put(tmp_path, _mk_summary(run_id="r_new", generated_at="2026-11-09T00:00:00"))
        summaries, warnings = scan_summaries(
            str(tmp_path), since=datetime(2026, 6, 1))
        assert [s["run_id"] for s in summaries] == ["r_new"]
        assert warnings == []  # 时间窗排除是正常过滤，不是坏数据


class TestAggregate:
    """聚合数学与结构：加权、归因、空输入安全。"""

    def test_pass_rate_weighted_not_mean(self):
        # 引擎A 1/9（11.11%）+ 引擎B 9/10（90%）：加权 10/19=52.63%，
        # 取平均则是 50.56%——两者必须可区分
        a = _mk_summary(engine="agent_behavior", total=9, passed=1, failed=8, failures=[])
        b = _mk_summary(engine="rest_api", run_id="r2", total=10, passed=9, failed=1, failures=[])
        agg = aggregate([a, b])
        assert agg["overall"]["pass_rate"] == pytest.approx(52.63)
        assert agg["by_engine"]["agent_behavior"]["pass_rate"] == pytest.approx(11.11)

    def test_failures_carry_engine_and_run(self):
        s = _mk_summary(engine="rest_api", run_id="r5")
        agg = aggregate([s])
        f = agg["failures"][0]
        assert f["engine"] == "rest_api" and f["run_id"] == "r5" and f["case_id"] == "c1"

    def test_window_bounds(self):
        old = _mk_summary(generated_at="2026-11-01T08:00:00")
        new = _mk_summary(run_id="r2", generated_at="2026-11-09T09:00:00")
        agg = aggregate([old, new])
        assert agg["window"]["from"].startswith("2026-11-01")
        assert agg["window"]["to"].startswith("2026-11-09")

    def test_empty_input_no_divide_by_zero(self):
        agg = aggregate([])
        assert agg["overall"]["total"] == 0 and agg["overall"]["pass_rate"] == 0.0
        assert agg["by_engine"] == {} and agg["failures"] == []

    def test_warnings_embedded_in_sources(self):
        detail = [{"path": "p", "reason": "r"}]
        agg = aggregate([_mk_summary(failures=[])], warnings=detail)
        assert agg["sources"]["warnings"] == 1
        assert agg["sources"]["warning_detail"] == detail


class TestOutput:
    """落盘与渲染。"""

    def test_write_aggregate_roundtrip(self, tmp_path):
        agg = aggregate([_mk_summary()])
        path = write_aggregate(agg, out_root=os.path.join(str(tmp_path), "aggregate"))
        assert os.path.isfile(path)
        data = json.loads(open(path, encoding="utf-8").read())
        assert data["aggregate_id"] == agg["aggregate_id"]
        assert data["schema_version"] == "1.0"

    def test_render_console_lists_engines_and_warnings(self):
        agg = aggregate(
            [_mk_summary(engine="rest_api")],
            warnings=[{"path": "x", "reason": "y"}],
        )
        text = render_console(agg)
        assert "rest_api" in text and "坏数据 1 条" in text and "失败清单" in text
