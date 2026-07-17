"""
定位策略模块。

设计模式：策略模式（Strategy）
"""
from .base import LocatorStrategy
from .css import CSSLocator
from .xpath import XPathLocator
from .test_id import TestIdLocator
from .text import TextLocator
from .role import RoleLocator
from .placeholder import PlaceholderLocator
from .label import LabelLocator
from .alt import AltLocator
from .title import TitleLocator
from .composite import CompositeLocator

__all__ = [
    "LocatorStrategy",
    "CSSLocator",
    "XPathLocator",
    "TestIdLocator",
    "TextLocator",
    "RoleLocator",
    "PlaceholderLocator",
    "LabelLocator",
    "AltLocator",
    "TitleLocator",
    "CompositeLocator",
]