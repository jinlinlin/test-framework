"""
文件上传操作。

设计模式：命令模式（Command）
"""
from __future__ import annotations

from typing import Any, List, Union

from .base import UIAction


class UploadAction(UIAction):
    """文件上传操作"""

    def __init__(self, selector: str, file_path: Union[str, List[str]], **kwargs: Any) -> None:
        super().__init__(selector, **kwargs)
        self._file_path = file_path

    async def execute(self, page) -> None:
        await page.set_input_files(self._selector, self._file_path, **self._kwargs)

    @property
    def name(self) -> str:
        return "upload"