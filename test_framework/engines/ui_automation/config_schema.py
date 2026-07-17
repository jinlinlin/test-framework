"""
UI自动化测试配置Schema。

使用pydantic定义配置结构，确保配置合法性。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BrowserConfig(BaseModel):
    """浏览器配置"""
    browser_type: str = Field(default="chromium", description="浏览器类型: chromium/firefox/webkit")
    headless: bool = Field(default=True, description="是否无头模式")
    viewport_width: int = Field(default=1920, description="视口宽度")
    viewport_height: int = Field(default=1080, description="视口高度")
    device_scale_factor: float = Field(default=1.0, description="设备缩放因子")
    locale: str = Field(default="zh-CN", description="语言环境")
    timezone_id: str = Field(default="Asia/Shanghai", description="时区")
    user_agent: Optional[str] = Field(default=None, description="用户代理")
    slow_mo: int = Field(default=0, description="操作延迟(ms)")
    timeout: int = Field(default=30000, description="默认超时(ms)")
    ignore_https_errors: bool = Field(default=False, description="忽略HTTPS错误")


class TraceConfig(BaseModel):
    """追踪配置"""
    enabled: bool = Field(default=False, description="是否启用追踪")
    screenshots: bool = Field(default=True, description="是否包含截图")
    snapshots: bool = Field(default=True, description="是否包含快照")
    sources: bool = Field(default=True, description="是否包含源码")


class VideoConfig(BaseModel):
    """视频录制配置"""
    enabled: bool = Field(default=False, description="是否启用视频录制")
    dir: Optional[str] = Field(default=None, description="视频保存目录")


class ScreenshotConfig(BaseModel):
    """截图配置"""
    on_failure: bool = Field(default=True, description="失败时自动截图")
    full_page: bool = Field(default=True, description="是否全页截图")
    dir: Optional[str] = Field(default=None, description="截图保存目录")


class NetworkConfig(BaseModel):
    """网络配置"""
    record_har: bool = Field(default=False, description="是否录制HAR")
    har_path: Optional[str] = Field(default=None, description="HAR文件路径")
    intercept_enabled: bool = Field(default=False, description="是否启用网络拦截")


class UIAutomationConfig(BaseModel):
    """UI自动化测试配置"""
    browser: BrowserConfig = Field(default_factory=BrowserConfig, description="浏览器配置")
    trace: TraceConfig = Field(default_factory=TraceConfig, description="追踪配置")
    video: VideoConfig = Field(default_factory=VideoConfig, description="视频配置")
    screenshot: ScreenshotConfig = Field(default_factory=ScreenshotConfig, description="截图配置")
    network: NetworkConfig = Field(default_factory=NetworkConfig, description="网络配置")
    retry_count: int = Field(default=3, description="重试次数")
    report_dir: str = Field(default="reports", description="报告目录")