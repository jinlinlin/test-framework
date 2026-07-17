"""
core.pipeline 包 — 管道执行引擎（责任链模式）。

提供管道、阶段、过滤器和钩子系统。
"""
from .context import PipelineContext
from .filter import Filter, TagFilter
from .hooks import HookManager
from .pipeline import Pipeline
from .stage import Stage

__all__ = [
    "Pipeline",
    "Stage",
    "PipelineContext",
    "Filter",
    "TagFilter",
    "HookManager",
]
