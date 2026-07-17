# -*- coding: utf-8 -*-
"""Pipeline 单元测试。

测试管道 Stage 注册、Filter 过滤、执行流程。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
import asyncio


class TestPipeline:
    """测试 Pipeline 责任链执行。"""

    def test_add_stage(self):
        """测试添加阶段到管道。"""
        from test_framework.core.pipeline.pipeline import Pipeline

        pipeline = Pipeline()
        mock_stage = MagicMock()
        mock_stage.name = "test_stage"

        pipeline.add_stage(mock_stage)
        assert len(pipeline._stages) == 1

    def test_add_filter(self):
        """测试添加过滤器。"""
        from test_framework.core.pipeline.pipeline import Pipeline

        pipeline = Pipeline()
        mock_filter = MagicMock()
        pipeline.add_filter(mock_filter)
        assert len(pipeline._filters) == 1

    def test_pipeline_context_creation(self):
        """测试 PipelineContext 初始化。"""
        from test_framework.core.pipeline.pipeline_context import PipelineContext

        ctx = PipelineContext(data={"key": "value"})
        assert ctx.data["key"] == "value"
        assert ctx.metadata == {}

    def test_stage_execution_order(self):
        """测试阶段按添加顺序执行。"""
        from test_framework.core.pipeline.pipeline import Pipeline
        from test_framework.core.pipeline.stage import Stage

        call_order = []

        class StageA(Stage):
            @property
            def name(self):
                return "stage_a"

            async def execute(self, context):
                call_order.append("A")
                return context

        class StageB(Stage):
            @property
            def name(self):
                return "stage_b"

            async def execute(self, context):
                call_order.append("B")
                return context

        pipeline = Pipeline()
        pipeline.add_stage(StageA())
        pipeline.add_stage(StageB())

        asyncio.get_event_loop().run_until_complete(
            pipeline.execute(MagicMock())
        )
        assert call_order == ["A", "B"]
