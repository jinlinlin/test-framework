"""
UI测试套件模块。

包含冒烟、回归、端到端和视觉回归测试套件。
"""
from .smoke_ui import SmokeUISuite
from .regression_ui import RegressionUISuite
from .e2e_ui import E2EUISuite
from .visual_ui import VisualUISuite

__all__ = [
    "SmokeUISuite",
    "RegressionUISuite",
    "E2EUISuite",
    "VisualUISuite",
]