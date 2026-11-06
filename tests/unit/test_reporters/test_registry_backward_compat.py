# -*- coding: utf-8 -*-
"""报告器注册表向后兼容回归测试。

覆盖两条契约：
1. 签名探测分发：新 Reporter（声明 run_id/engine 或 **kwargs）拿到新参数，
   旧签名 Reporter 一字不改继续可用，不抛 unexpected keyword TypeError。
2. 引擎完成通知链：notify_engine_completed 触达所有 Reporter，
   默认 no-op 的实现不受影响。
"""
import asyncio
import json

from test_framework.reporters.base import BaseReporter
from test_framework.reporters.reporter_registry import ReporterRegistry
from test_framework.reporters.json.reporter import JSONReporter


class LegacyReporter(BaseReporter):
    """模拟已存在的、用旧签名 override 的第三方 Reporter（无新参数）。"""

    @property
    def reporter_type(self) -> str:
        return "legacy"

    async def on_test_completed(self, result):
        pass

    async def on_plan_completed(self, plan_name, results):
        return f"legacy://{plan_name}"


class ModernReporter(BaseReporter):
    """新签名 Reporter：显式声明 run_id/engine。"""

    @property
    def reporter_type(self) -> str:
        return "modern"

    async def on_test_completed(self, result):
        pass

    async def on_plan_completed(self, plan_name, results, run_id=None, engine=None):
        return f"modern://{engine}/{run_id}"

    async def on_engine_completed(self, engine, run_id, summary):
        self.last_summary = (engine, run_id, summary)


class KwargsReporter(BaseReporter):
    """接受 **kwargs 的 Reporter 也应被探测为新签名。"""

    @property
    def reporter_type(self) -> str:
        return "kwargs"

    async def on_test_completed(self, result):
        pass

    async def on_plan_completed(self, plan_name, results, **kwargs):
        return f"kwargs://{kwargs.get('engine')}/{kwargs.get('run_id')}"


class TestRegistryBackwardCompat:
    """generate_all_reports 的新旧 Reporter 双跑兼容。"""

    def test_dispatches_both_without_breaking(self):
        """同一注册表内旧签名与新签名 Reporter 并存，均正常分发。"""
        async def scenario():
            reg = ReporterRegistry()
            reg.register(LegacyReporter())
            reg.register(ModernReporter())
            reg.register(KwargsReporter())
            paths = await reg.generate_all_reports(
                "p", [], run_id="2026-11-06_143022_abc123", engine="agent_behavior",
            )
            assert paths["legacy"] == "legacy://p"
            assert paths["modern"] == "modern://agent_behavior/2026-11-06_143022_abc123"
            assert paths["kwargs"] == "kwargs://agent_behavior/2026-11-06_143022_abc123"

        asyncio.run(scenario())

    def test_legacy_only_caller_unaffected(self):
        """旧调用方不传 run_id/engine，新签名 Reporter 也能正常收到 None。"""
        async def scenario():
            reg = ReporterRegistry()
            reg.register(LegacyReporter())
            reg.register(ModernReporter())
            paths = await reg.generate_all_reports("p", [])
            assert paths["legacy"] == "legacy://p"
            assert paths["modern"] == "modern://None/None"

        asyncio.run(scenario())

    def test_signature_probe_cached_per_class(self):
        """探测结果按类缓存：同类第二个实例不再重复 introspect。"""
        first = ModernReporter()
        assert ReporterRegistry._accepts_new_params(first) is True
        assert ModernReporter in ReporterRegistry._SUPPORTS_NEW_PARAMS
        second = ModernReporter()
        assert ReporterRegistry._accepts_new_params(second) is True
        assert LegacyReporter.__name__  # 触发类存在性即可
        assert ReporterRegistry._accepts_new_params(LegacyReporter()) is False

    def test_notify_engine_completed_chain(self):
        """引擎完成通知触达全部 Reporter：覆盖者收到、未覆盖者走默认 no-op。"""
        async def scenario():
            reg = ReporterRegistry()
            legacy = LegacyReporter()
            modern = ModernReporter()
            reg.register(legacy)
            reg.register(modern)
            summary = {"schema_version": "1.0", "totals": {"total": 3}}
            await reg.notify_engine_completed("agent_behavior", "run-1", summary)
            assert modern.last_summary == ("agent_behavior", "run-1", summary)
            # LegacyReporter 未覆盖 on_engine_completed，默认 no-op 不抛异常
            assert not hasattr(legacy, "last_summary")

        asyncio.run(scenario())


class TestJsonReporterEngineArtifacts:
    """JSONReporter 的引擎维度与 Layer 2 summary.json 出口。"""

    def test_full_backward_compat_without_run_dims(self, tmp_path, monkeypatch):
        """不提供 engine/run_id：输出结构与旧版一致，且不产出 artifacts 目录。"""
        monkeypatch.chdir(tmp_path)

        async def scenario():
            reporter = JSONReporter(output_dir=str(tmp_path / "json"))
            path = await reporter.on_plan_completed("p", [{"status": "passed"}])
            with open(path, encoding="utf-8") as f:
                report = json.load(f)
            assert set(report) == {"plan_name", "generated_at", "summary", "results"}
            assert not (tmp_path / "artifacts").exists()

        asyncio.run(scenario())

    def test_summary_json_emitted_with_run_dims(self, tmp_path, monkeypatch):
        """提供 engine+run_id：plan 报告带运行字段，且按约定产出 summary.json。"""
        monkeypatch.chdir(tmp_path)

        async def scenario():
            reporter = JSONReporter(output_dir=str(tmp_path / "json"))
            results = [
                {"case_id": "c1", "status": "passed", "duration": 1, "message": ""},
                {"case_id": "c2", "status": "failed", "duration": 2, "message": "boom"},
            ]
            path = await reporter.on_plan_completed(
                "p", results, run_id="run-1", engine="agent_behavior",
            )
            with open(path, encoding="utf-8") as f:
                report = json.load(f)
            assert report["engine"] == "agent_behavior"
            assert report["run_id"] == "run-1"

            summary_path = tmp_path / "artifacts" / "agent_behavior" / "run-1" / "summary.json"
            assert summary_path.exists()
            with open(summary_path, encoding="utf-8") as f:
                summary = json.load(f)
            assert summary["schema_version"] == "1.0"
            assert summary["engine"] == "agent_behavior"
            assert summary["run_id"] == "run-1"
            assert summary["totals"]["total"] == 2
            assert summary["totals"]["failed"] == 1
            assert [x["case_id"] for x in summary["failures"]] == ["c2"]

        asyncio.run(scenario())

    def test_registry_passthrough_to_json_reporter(self, tmp_path, monkeypatch):
        """经注册表分发（签名探测路径）时，JSONReporter 作为新签名 Reporter 收到透传值。"""
        monkeypatch.chdir(tmp_path)

        async def scenario():
            reg = ReporterRegistry()
            reporter = JSONReporter(
                output_dir=str(tmp_path / "json"),
                engine="agent_behavior",   # 实例级回退值也应生效（run_id 走透传）
            )
            reg.register(reporter)
            paths = await reg.generate_all_reports(
                "p", [{"status": "passed"}], run_id="run-9",
            )
            assert "json" in paths
            assert (tmp_path / "artifacts" / "agent_behavior" / "run-9" / "summary.json").exists()

        asyncio.run(scenario())
