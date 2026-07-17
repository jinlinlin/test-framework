"""
UI操作模块。

设计模式：命令模式（Command）
"""
from .base import UIAction
from .click import ClickAction
from .dblclick import DoubleClickAction
from .rightclick import RightClickAction
from .fill import FillAction
from .type import TypeAction
from .clear import ClearAction
from .hover import HoverAction
from .drag import DragAction
from .scroll import ScrollAction
from .select import SelectAction
from .check import CheckAction
from .uncheck import UncheckAction
from .upload import UploadAction
from .focus import FocusAction
from .blur import BlurAction
from .press import PressAction
from .screenshot import ScreenshotAction
from .wait import WaitAction
from .composite import CompositeAction

__all__ = [
    "UIAction",
    "ClickAction",
    "DoubleClickAction",
    "RightClickAction",
    "FillAction",
    "TypeAction",
    "ClearAction",
    "HoverAction",
    "DragAction",
    "ScrollAction",
    "SelectAction",
    "CheckAction",
    "UncheckAction",
    "UploadAction",
    "FocusAction",
    "BlurAction",
    "PressAction",
    "ScreenshotAction",
    "WaitAction",
    "CompositeAction",
]