"""
请求构建器 — 建造者模式。

职责：链式构建 HTTP 请求，支持参数、请求头、Body、文件上传。
设计模式：建造者模式（Builder Pattern）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Request:
    """
    HTTP 请求数据对象。

    Attributes:
        method: HTTP 方法（GET / POST / PUT / DELETE / PATCH）。
        path: 请求路径。
        headers: 请求头字典。
        params: URL 查询参数。
        body: 请求体（JSON / 表单）。
        files: 文件上传字段。
    """

    method: str = "GET"
    path: str = "/"
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    body: Any = None
    files: Dict[str, str] = field(default_factory=dict)


class RequestBuilder:
    """
    请求构建器（建造者模式）。

    通过链式调用逐步设置请求的各个组成部分，
    最终调用 build() 生成不可变的 Request 对象。

    Example::

        request = (RequestBuilder()
                   .method("POST")
                   .path("/api/users")
                   .header("Content-Type", "application/json")
                   .json_body({"name": "test"})
                   .build())
    """

    def __init__(self) -> None:
        """初始化构建器，所有字段设为默认值。"""
        self._method: str = "GET"
        self._path: str = "/"
        self._headers: Dict[str, str] = {}
        self._params: Dict[str, Any] = {}
        self._body: Any = None
        self._files: Dict[str, str] = {}

    # ===== 链式设置方法 =====

    def method(self, m: str) -> "RequestBuilder":
        """
        设置 HTTP 方法。

        Args:
            m: HTTP 方法字符串（GET / POST / PUT / DELETE / PATCH）。

        Returns:
            self，支持链式调用。
        """
        self._method = m.upper()
        return self

    def path(self, p: str) -> "RequestBuilder":
        """
        设置请求路径。

        Args:
            p: URL 路径。

        Returns:
            self。
        """
        self._path = p
        return self

    def header(self, key: str, value: str) -> "RequestBuilder":
        """
        添加单个请求头。

        Args:
            key: 请求头名称。
            value: 请求头值。

        Returns:
            self。
        """
        self._headers[key] = value
        return self

    def headers(self, h: Dict[str, str]) -> "RequestBuilder":
        """
        批量设置请求头。

        Args:
            h: 请求头字典。

        Returns:
            self。
        """
        self._headers.update(h)
        return self

    def param(self, key: str, value: Any) -> "RequestBuilder":
        """
        添加单个 URL 查询参数。

        Args:
            key: 参数名。
            value: 参数值。

        Returns:
            self。
        """
        self._params[key] = value
        return self

    def params(self, p: Dict[str, Any]) -> "RequestBuilder":
        """
        批量设置 URL 查询参数。

        Args:
            p: 参数字典。

        Returns:
            self。
        """
        self._params.update(p)
        return self

    def json_body(self, body: Any) -> "RequestBuilder":
        """
        设置 JSON 请求体。

        Args:
            body: JSON 可序列化的对象。

        Returns:
            self。
        """
        self._body = body
        self._headers.setdefault("Content-Type", "application/json")
        return self

    def form_body(self, body: Dict[str, str]) -> "RequestBuilder":
        """
        设置表单请求体。

        Args:
            body: 表单字段字典。

        Returns:
            self。
        """
        self._body = body
        self._headers.setdefault(
            "Content-Type", "application/x-www-form-urlencoded"
        )
        return self

    def file(self, fld: str, path: str) -> "RequestBuilder":
        """
        添加文件上传字段。

        Args:
            fld: 表单字段名。
            path: 文件路径。

        Returns:
            self。
        """
        self._files[fld] = path
        return self

    # ===== 构建 =====

    def build(self) -> Request:
        """
        构建并返回 Request 数据对象。

        Returns:
            构建完成的 Request 实例。
        """
        return Request(
            method=self._method,
            path=self._path,
            headers=dict(self._headers),
            params=dict(self._params),
            body=self._body,
            files=dict(self._files),
        )

    # ===== 工厂方法 =====

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "RequestBuilder":
        """
        从配置字典快速构建 RequestBuilder。

        支持的配置键::

            {
                "method": "POST",
                "path": "/api/users",
                "headers": {"X-Token": "abc"},
                "params": {"page": 1},
                "body": {"name": "test"},
                "body_type": "json" | "form",
                "files": {"upload": "/path/to/file"}
            }

        Args:
            config: 请求配置字典。

        Returns:
            配置好的 RequestBuilder 实例。
        """
        builder = cls()

        # HTTP 方法
        if "method" in config:
            builder.method(config["method"])

        # 请求路径
        if "path" in config:
            builder.path(config["path"])
        elif "url" in config:
            builder.path(config["url"])

        # 请求头
        if "headers" in config:
            builder.headers(config["headers"])

        # 查询参数
        if "params" in config:
            builder.params(config["params"])
        elif "query" in config:
            builder.params(config["query"])

        # 请求体
        body_type = config.get("body_type", "json")
        if "body" in config:
            if body_type == "form":
                builder.form_body(config["body"])
            else:
                builder.json_body(config["body"])
        elif "json" in config:
            builder.json_body(config["json"])
        elif "data" in config:
            builder.form_body(config["data"])

        # 文件上传
        if "files" in config:
            for fld_name, file_path in config["files"].items():
                builder.file(fld_name, file_path)

        return builder
