"""
IPC 通信桥接 — Python ↔ Node.js 双向通信。

职责：使用 Unix Domain Socket / Named Pipe 实现低延迟数据交换，
      支持请求-响应模式的同步调用。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class IPCBridge:
    """
    IPC 双向通信桥接器。

    在 Python 端启动一个 Unix Domain Socket（Linux/Mac）
    或 Named Pipe（Windows）服务端，与 Node.js 进程进行
    JSON 消息的双向通信。

    Attributes:
        _socket_path: Socket 文件路径。
        _server: asyncio 服务端实例。
        _connected: 连接状态标志。
    """

    def __init__(self, socket_path: Optional[str] = None) -> None:
        """
        初始化 IPC 桥接器。

        Args:
            socket_path: Socket 路径，默认自动生成临时路径。
        """
        if socket_path is None:
            if sys.platform == "win32":
                # Windows 使用 Named Pipe
                self._socket_path = r"\\.\pipe\uniplore_ipc_" + str(os.getpid())
            else:
                # Unix 使用 Domain Socket
                self._socket_path = os.path.join(
                    tempfile.gettempdir(),
                    f"uniplore_ipc_{os.getpid()}.sock"
                )
        else:
            self._socket_path = socket_path

        self._server: Optional[asyncio.AbstractServer] = None
        self._connected: bool = False
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def start(self) -> None:
        """
        启动 IPC 服务端。

        创建 Socket 并监听 Node.js 客户端连接。
        """
        # 清理旧的 socket 文件（Unix 系统）
        if sys.platform != "win32" and os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

        if sys.platform == "win32":
            # Windows Named Pipe 暂不支持，使用 TCP 回退
            self._server = await asyncio.start_server(
                self._handle_client, "127.0.0.1", 0
            )
        else:
            self._server = await asyncio.start_unix_server(
                self._handle_client, path=self._socket_path
            )

        self._connected = True
        logger.info(f"IPC 服务端已启动: {self._socket_path}")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        处理客户端连接。

        Args:
            reader: 流读取器。
            writer: 流写入器。
        """
        self._reader = reader
        self._writer = writer
        logger.debug("IPC 客户端已连接")

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                message = json.loads(data.decode("utf-8"))
                await self._response_queue.put(message)
        except (json.JSONDecodeError, asyncio.CancelledError):
            pass
        finally:
            logger.debug("IPC 客户端已断开")

    async def send(self, message: Dict[str, Any], timeout: float = 30) -> Dict[str, Any]:
        """
        发送消息并等待响应。

        Args:
            message: 要发送的消息字典。
            timeout: 等待响应的超时时间（秒）。

        Returns:
            响应消息字典。

        Raises:
            ConnectionError: 未连接时抛出。
            TimeoutError: 等待响应超时。
        """
        if not self._writer:
            raise ConnectionError("IPC 未连接，请先调用 start()")

        # 发送 JSON 消息（以换行符分隔）
        data = json.dumps(message, ensure_ascii=False) + "\n"
        self._writer.write(data.encode("utf-8"))
        await self._writer.drain()

        # 等待响应
        try:
            response = await asyncio.wait_for(
                self._response_queue.get(), timeout=timeout
            )
            return response
        except asyncio.TimeoutError:
            raise TimeoutError(f"IPC 响应超时: {timeout}s")

    async def stop(self) -> None:
        """关闭 IPC 服务端并清理资源。"""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # 清理 Unix socket 文件
        if sys.platform != "win32" and os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

        self._connected = False
        logger.info("IPC 服务端已关闭")

    async def is_connected(self) -> bool:
        """
        检查 IPC 连接状态。

        Returns:
            True 表示已连接可用。
        """
        return self._connected and self._writer is not None

    @property
    def socket_path(self) -> str:
        """获取 Socket 路径。"""
        return self._socket_path
