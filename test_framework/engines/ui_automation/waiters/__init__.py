"""
等待策略模块。

设计模式：策略模式（Strategy）
"""
from .base import WaiterStrategy
from .visibility import VisibilityWaiter
from .presence import PresenceWaiter
from .hidden import HiddenWaiter
from .clickable import ClickableWaiter
from .enabled import EnabledWaiter
from .text_change import TextChangeWaiter
from .network_idle import NetworkIdleWaiter
from .load_state import LoadStateWaiter
from .url_change import URLChangeWaiter
from .navigation import NavigationWaiter
from .response import ResponseWaiter
from .request import RequestWaiter
from .console_log import ConsoleLogWaiter
from .custom import CustomWaiter
from .composite import CompositeWaiter

__all__ = [
    "WaiterStrategy",
    "VisibilityWaiter",
    "PresenceWaiter",
    "HiddenWaiter",
    "ClickableWaiter",
    "EnabledWaiter",
    "TextChangeWaiter",
    "NetworkIdleWaiter",
    "LoadStateWaiter",
    "URLChangeWaiter",
    "NavigationWaiter",
    "ResponseWaiter",
    "RequestWaiter",
    "ConsoleLogWaiter",
    "CustomWaiter",
    "CompositeWaiter",
]