"""
core.interfaces 包 — 框架接口契约定义。

导出所有核心接口，供其他模块实现或引用。
"""
from .adaptable import IAdaptable
from .assertable import IAssertable
from .configurable import IConfigurable
from .element_locatable import IElementLocatable
from .executable import IExecutable
from .lifecycle import ILifecycle
from .observable import IObservable
from .pluggable import IPluggable
from .reportable import IReportable
from .testable import ITestable
from .ui_interactable import IUIInteractable

__all__ = [
    "ITestable",
    "IAdaptable",
    "IReportable",
    "IConfigurable",
    "IExecutable",
    "IObservable",
    "ILifecycle",
    "IPluggable",
    "IAssertable",
    "IElementLocatable",
    "IUIInteractable",
]
