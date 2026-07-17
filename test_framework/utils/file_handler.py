"""
文件处理工具 — 提供文件读写、目录操作、临时文件管理。

职责：封装常用的文件 I/O 操作，支持 JSON / YAML / CSV 格式。
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FileHandler:
    """
    文件处理工具类。

    使用示例::

        handler = FileHandler()
        data = handler.read_json("config.json")
        handler.write_json("output.json", data, indent=2)
    """

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    @staticmethod
    def read_json(file_path: str) -> Any:
        """
        读取 JSON 文件。

        Args:
            file_path: 文件路径。

        Returns:
            解析后的 Python 对象。
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def write_json(
        file_path: str, data: Any, indent: int = 2, ensure_ascii: bool = False
    ) -> None:
        """写入 JSON 文件。"""
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)

    # ------------------------------------------------------------------
    # YAML
    # ------------------------------------------------------------------

    @staticmethod
    def read_yaml(file_path: str) -> Any:
        """读取 YAML 文件（需要 PyYAML）。"""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML 未安装，使用 JSON 降级读取")
            return FileHandler.read_json(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def write_yaml(file_path: str, data: Any, default_flow_style: bool = False) -> None:
        """写入 YAML 文件（需要 PyYAML）。"""
        try:
            import yaml
        except ImportError:
            logger.warning("PyYAML 未安装，使用 JSON 降级写入")
            FileHandler.write_json(file_path, data)
            return

        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=default_flow_style, allow_unicode=True)

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    @staticmethod
    def read_csv(file_path: str) -> List[Dict[str, str]]:
        """读取 CSV 文件为字典列表。"""
        with open(file_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return list(reader)

    @staticmethod
    def write_csv(file_path: str, data: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
        """写入 CSV 文件。"""
        if not data:
            return
        fieldnames = fieldnames or list(data[0].keys())
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    # ------------------------------------------------------------------
    # 文本文件
    # ------------------------------------------------------------------

    @staticmethod
    def read_text(file_path: str, encoding: str = "utf-8") -> str:
        """读取文本文件。"""
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()

    @staticmethod
    def write_text(file_path: str, content: str, encoding: str = "utf-8") -> None:
        """写入文本文件。"""
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)

    # ------------------------------------------------------------------
    # 目录与临时文件
    # ------------------------------------------------------------------

    @staticmethod
    def ensure_dir(dir_path: str) -> str:
        """确保目录存在，不存在则创建。"""
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    @staticmethod
    def create_temp_file(suffix: str = ".tmp", content: str = "") -> str:
        """创建临时文件并返回路径。"""
        fd, path = tempfile.mkstemp(suffix=suffix)
        if content:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            os.close(fd)
        return path

    @staticmethod
    def create_temp_dir(prefix: str = "tf_") -> str:
        """创建临时目录并返回路径。"""
        return tempfile.mkdtemp(prefix=prefix)

    @staticmethod
    def copy_file(src: str, dst: str) -> str:
        """复制文件。"""
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        return shutil.copy2(src, dst)

    @staticmethod
    def safe_remove(path: str) -> bool:
        """安全删除文件或目录。"""
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.exists(path):
                os.remove(path)
            return True
        except OSError as e:
            logger.error(f"删除失败: {path} — {e}")
            return False
