"""
消息队列适配器统一接口。

职责：定义消息队列操作的统一抽象，
      包含消息发布、消费、主题管理等方法。
      支持 Kafka / RabbitMQ 两种消息中间件。
"""
from __future__ import annotations

import time
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

from ..base import BaseAdapter


@dataclass
class Message:
    """
    消息数据对象。

    Attributes:
        topic: 主题名称。
        key: 消息键（可选）。
        value: 消息体（字节或字符串）。
        headers: 消息头字典。
        partition: 分区号（Kafka）。
        offset: 消息偏移量（Kafka）。
        timestamp: 消息时间戳。
        exchange: 交换机名称（RabbitMQ）。
        routing_key: 路由键（RabbitMQ）。
    """

    topic: str = ""
    key: Optional[str] = None
    value: Any = None
    headers: Dict[str, str] = field(default_factory=dict)
    partition: int = 0
    offset: int = 0
    timestamp: float = 0.0
    exchange: str = ""
    routing_key: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class TopicInfo:
    """
    主题信息。

    Attributes:
        name: 主题名称。
        partitions: 分区数。
        replication_factor: 副本因子。
        config: 主题配置。
    """

    name: str = ""
    partitions: int = 1
    replication_factor: int = 1
    config: Dict[str, str] = field(default_factory=dict)


# 消息处理回调类型
MessageHandler = Callable[[Message], Coroutine[Any, Any, None]]


class MessagingAdapter(BaseAdapter):
    """
    消息队列适配器抽象基类。

    定义消息发布、消费、主题管理等统一方法。
    """

    @property
    def adapter_type(self) -> str:
        return "messaging"

    # ===== 消息发布 =====

    @abstractmethod
    async def publish(
        self,
        topic: str,
        value: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        发布消息。

        Args:
            topic: 主题名称。
            value: 消息体。
            key: 消息键（用于分区路由）。
            headers: 消息头。
        """
        ...

    @abstractmethod
    async def publish_batch(
        self,
        topic: str,
        messages: List[Dict[str, Any]],
    ) -> int:
        """
        批量发布消息。

        Args:
            topic: 主题名称。
            messages: 消息列表，每项包含 value/key/headers。

        Returns:
            成功发布的消息数。
        """
        ...

    # ===== 消息消费 =====

    @abstractmethod
    async def subscribe(self, topics: List[str], group_id: str = "") -> None:
        """
        订阅主题。

        Args:
            topics: 主题名称列表。
            group_id: 消费者组 ID。
        """
        ...

    @abstractmethod
    async def consume(
        self,
        max_messages: int = 100,
        timeout: float = 10.0,
    ) -> List[Message]:
        """
        拉取消息。

        Args:
            max_messages: 最大拉取消息数。
            timeout: 超时秒数。

        Returns:
            消息列表。
        """
        ...

    @abstractmethod
    async def consume_with_handler(
        self,
        handler: MessageHandler,
        max_messages: int = 0,
    ) -> None:
        """
        使用回调函数消费消息。

        Args:
            handler: 异步消息处理函数。
            max_messages: 最大消费数（0 表示无限循环）。
        """
        ...

    @abstractmethod
    async def unsubscribe(self) -> None:
        """取消订阅。"""
        ...

    # ===== 主题管理 =====

    @abstractmethod
    async def create_topic(
        self,
        topic: str,
        partitions: int = 1,
        replication_factor: int = 1,
        config: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        创建主题。

        Args:
            topic: 主题名称。
            partitions: 分区数。
            replication_factor: 副本因子。
            config: 主题配置。
        """
        ...

    @abstractmethod
    async def delete_topic(self, topic: str) -> None:
        """删除主题。"""
        ...

    @abstractmethod
    async def list_topics(self) -> List[TopicInfo]:
        """列出所有主题。"""
        ...

    # ===== 偏移量管理 =====

    @abstractmethod
    async def commit_offset(self, topic: str, partition: int, offset: int) -> None:
        """
        提交消费偏移量。

        Args:
            topic: 主题名称。
            partition: 分区号。
            offset: 偏移量。
        """
        ...

    @abstractmethod
    async def get_offset(self, topic: str, partition: int) -> Dict[str, int]:
        """
        获取偏移量信息。

        Args:
            topic: 主题名称。
            partition: 分区号。

        Returns:
            包含 low / high / committed 的偏移量字典。
        """
        ...
