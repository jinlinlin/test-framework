"""报告层子包 — HTML/JSON/Console/Allure 报告 + 外部集成。"""
from .base import BaseReporter
from .reporter_factory import ReporterFactory
from .reporter_registry import ReporterRegistry

__all__ = ["BaseReporter", "ReporterFactory", "ReporterRegistry"]
