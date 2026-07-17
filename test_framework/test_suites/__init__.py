"""
测试套件模块。

包含UI、API和组合测试套件。
"""
from .ui_suites import SmokeUISuite, RegressionUISuite, E2EUISuite, VisualUISuite
from .api_suites import SmokeAPISuite, RegressionAPISuite, ContractAPISuite
from .combined_suites import FullE2ESuite

__all__ = [
    "SmokeUISuite",
    "RegressionUISuite",
    "E2EUISuite",
    "VisualUISuite",
    "SmokeAPISuite",
    "RegressionAPISuite",
    "ContractAPISuite",
    "FullE2ESuite",
]