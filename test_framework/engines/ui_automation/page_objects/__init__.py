"""
Page Object模块。

包含页面和组件的定义。
"""
from .login_page import LoginPage
from .dashboard_page import DashboardPage

__all__ = [
    "LoginPage",
    "DashboardPage",
]