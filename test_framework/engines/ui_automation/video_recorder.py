"""
视频录制器。

封装浏览器视频录制功能。
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class VideoRecorder:
    """
    视频录制器

    封装浏览器视频录制功能。
    """

    def __init__(self) -> None:
        self._enabled = False
        self._video_dir: Optional[str] = None

    def enable(self, video_dir: str) -> None:
        """
        启用视频录制

        Args:
            video_dir: 视频保存目录
        """
        self._enabled = True
        self._video_dir = video_dir
        logger.info(f"Video recording enabled, saving to: {video_dir}")

    def disable(self) -> None:
        """禁用视频录制"""
        self._enabled = False
        self._video_dir = None
        logger.info("Video recording disabled")

    @property
    def enabled(self) -> bool:
        """是否启用"""
        return self._enabled

    @property
    def video_dir(self) -> Optional[str]:
        """视频保存目录"""
        return self._video_dir