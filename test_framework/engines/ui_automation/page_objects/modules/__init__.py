"""
按功能模块划分的页面。
"""
from .user_management import UserListPage, UserCreatePage, UserEditPage
from .order_management import OrderListPage
from .reporting import ReportViewer

__all__ = [
    "UserListPage",
    "UserCreatePage",
    "UserEditPage",
    "OrderListPage",
    "ReportViewer",
]