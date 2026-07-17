"""
UI断言模块。

设计模式：策略模式（Strategy）
"""
from .base import UIAssertion
from .visibility import VisibilityAssertion
from .text import TextAssertion
from .attribute import AttributeAssertion
from .css_property import CSSPropertyAssertion
from .count import CountAssertion
from .url import URLAssertion
from .title import TitleAssertion
from .enabled import EnabledAssertion
from .checked import CheckedAssertion
from .focused import FocusedAssertion
from .network import NetworkAssertion
from .console import ConsoleAssertion
from .composite import CompositeAssertion

__all__ = [
    "UIAssertion",
    "VisibilityAssertion",
    "TextAssertion",
    "AttributeAssertion",
    "CSSPropertyAssertion",
    "CountAssertion",
    "URLAssertion",
    "TitleAssertion",
    "EnabledAssertion",
    "CheckedAssertion",
    "FocusedAssertion",
    "NetworkAssertion",
    "ConsoleAssertion",
    "CompositeAssertion",
]