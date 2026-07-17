"""
可复用组件模块。

设计模式：组合模式（Composite）
"""
from .header import Header
from .sidebar import Sidebar
from .footer import Footer
from .modal import Modal
from .table import Table
from .form import Form
from .dropdown import Dropdown
from .tabs import Tabs
from .pagination import Pagination
from .toast import Toast
from .loading import Loading
from .menu import Menu

__all__ = [
    "Header",
    "Sidebar",
    "Footer",
    "Modal",
    "Table",
    "Form",
    "Dropdown",
    "Tabs",
    "Pagination",
    "Toast",
    "Loading",
    "Menu",
]