"""
基于 aio_pika 的 RabbitMQ 异步适配器。

特点：
- 纯异步 RabbitMQ 驱动（基于 aio-pika）
- 支持 Exchange/Queue 声明、消息发布、消费
- 支持消息持久化、确认机制
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .adapter import Message, MessageHandler, MessagingAdapter, TopicInfo

logger = logging.getLogger(__name__)


class RabbitMQAdapter(MessagingAdapter):
    """
    RabbitMQ 异步适配器。

    配置项::

        {
            "url": "amqp://guest:guest@localhost/",
            "exchange_name": "test_exchange",
            "exchange_type": "direct",      # direct / topic / fanout / headers
            "durable": True,
            "prefetch_count": 10,
        }
    """

    @property
    def implementation_name(self) -> str:
        return "rabbitmq"

    def __init__(self) -> None:
        """初始化 RabbitMQ 适配器。"""
        self._connection: Optional[Any] = None  # aio_pika.RobustConnection
        self._channel: Optional[Any] = None  # aio_pika.Channel
        self._exchange: Optional[Any] = None  # aio_pika.Exchange
        self._queue: Optional[Any] = None  # aio_pika.Queue
        self._config: Dict[str, Any] = {}

    async def connect(self, config: Dict[str, Any]) -> None:
        """
        创建 RabbitMQ 连接。

        Args:
            config: RabbitMQ 连接配置。
        """
        import aio_pika

        self._config = config
        url = config.get("url", "amqp://guest:guest@localhost/")

        self._connection = await aio_pika.connect_robust(url)
        self._channel = await self._connection.channel()

        # 设置预取数量
        prefetch = config.get("prefetch_count", 10)
        await self._channel.set_qos(prefetch_count=prefetch)

        # 声明交换机
        exchange_name = config.get("exchange_name", "test_exchange")
        exchange_type = config.get("exchange_type", "direct")
        durable = config.get("durable", True)

        type_map = {
            "direct": aio_pika.ExchangeType.DIRECT,
            "topic": aio_pika.ExchangeType.TOPIC,
            "fanout": aio_pika.ExchangeType.FANOUT,
            "headers": aio_pika.ExchangeType.HEADERS,
        }
        self._exchange = await self._channel.declare_exchange(
            name=exchange_name,
            type=type_map.get(exchange_type, aio_pika.ExchangeType.DIRECT),
            durable=durable,
        )

        logger.debug(f"RabbitMQAdapter 已连接: url={url}, exchange={exchange_name}")

    async def disconnect(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None
            self._channel = None
            self._exchange = None
            self._queue = None
        logger.debug("RabbitMQAdapter 已断开")

    async def is_connected(self) -> bool:
        if not self._connection:
            return False
        return not self._connection.is_closed

    # ===== 消息发布 =====

    async def publish(
        self,
        topic: str,
        value: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        if not self._exchange:
            raise RuntimeError("RabbitMQAdapter 未连接")

        import aio_pika

        # 序列化消息
        if isinstance(value, dict):
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        elif isinstance(value, str):
            body = value.encode("utf-8")
        elif isinstance(value, bytes):
            body = value
        else:
            body = str(value).encode("utf-8")

        message = aio_pika.Message(
            body=body,
            headers=headers or {},
            content_type="application/json" if isinstance(value, dict) else "text/plain",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        routing_key = key or topic
        await self._exchange.publish(message, routing_key=routing_key)

    async def publish_batch(
        self,
        topic: str,
        messages: List[Dict[str, Any]],
    ) -> int:
        count = 0
        for msg in messages:
            await self.publish(
                topic=topic,
                value=msg.get("value", ""),
                key=msg.get("key"),
                headers=msg.get("headers"),
            )
            count += 1
        return count

    # ===== 消息消费 =====

    async def subscribe(self, topics: List[str], group_id: str = "") -> None:
        if not self._channel:
            raise RuntimeError("RabbitMQAdapter 未连接")

        import aio_pika

        # 声明队列
        queue_name = group_id or "test_framework_queue"
        self._queue = await self._channel.declare_queue(
            queue_name,
            durable=True,
        )

        # 绑定路由键（每个 topic 作为路由键绑定到交换机）
        for topic in topics:
            await self._queue.bind(self._exchange, routing_key=topic)

        logger.debug(f"RabbitMQAdapter 已订阅: {topics}, queue={queue_name}")

    async def consume(
        self,
        max_messages: int = 100,
        timeout: float = 10.0,
    ) -> List[Message]:
        if not self._queue:
            raise RuntimeError("未订阅任何队列")

        messages: List[Message] = []
        try:
            async with self._queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        msg = Message(
                            topic=message.routing_key or "",
                            value=message.body.decode("utf-8") if message.body else None,
                            headers=dict(message.headers or {}),
                            exchange=message.exchange or "",
                            routing_key=message.routing_key or "",
                        )
                        messages.append(msg)
                        if len(messages) >= max_messages:
                            break
        except asyncio.TimeoutError:
            pass

        return messages

    async def consume_with_handler(
        self,
        handler: MessageHandler,
        max_messages: int = 0,
    ) -> None:
        if not self._queue:
            raise RuntimeError("未订阅任何队列")

        count = 0
        async with self._queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    msg = Message(
                        topic=message.routing_key or "",
                        value=message.body.decode("utf-8") if message.body else None,
                        headers=dict(message.headers or {}),
                        exchange=message.exchange or "",
                        routing_key=message.routing_key or "",
                    )
                    await handler(msg)
                    count += 1
                    if max_messages > 0 and count >= max_messages:
                        return

    async def unsubscribe(self) -> None:
        if self._queue:
            await self._queue.delete()
            self._queue = None

    # ===== 主题管理（RabbitMQ 中映射为 Exchange + Queue） =====

    async def create_topic(
        self,
        topic: str,
        partitions: int = 1,
        replication_factor: int = 1,
        config: Optional[Dict[str, str]] = None,
    ) -> None:
        """在 RabbitMQ 中创建队列并绑定到交换机。"""
        if not self._channel or not self._exchange:
            raise RuntimeError("RabbitMQAdapter 未连接")

        queue = await self._channel.declare_queue(topic, durable=True)
        await queue.bind(self._exchange, routing_key=topic)
        logger.debug(f"RabbitMQ 队列已创建并绑定: {topic}")

    async def delete_topic(self, topic: str) -> None:
        if not self._channel:
            return
        try:
            queue = await self._channel.get_queue(topic)
            await queue.delete()
        except Exception as e:
            logger.warning(f"删除队列失败: {e}")

    async def list_topics(self) -> List[TopicInfo]:
        """RabbitMQ 不提供直接的队列列表 API，返回空列表。"""
        logger.info("RabbitMQ 不支持直接列出所有队列，请使用管理 API")
        return []

    # ===== 偏移量管理（RabbitMQ 使用 ACK 机制，不需要手动偏移量管理） =====

    async def commit_offset(self, topic: str, partition: int, offset: int) -> None:
        """RabbitMQ 使用消息确认机制，无需手动提交偏移量。"""
        logger.debug("RabbitMQ 使用 ACK 机制，commit_offset 为空操作")

    async def get_offset(self, topic: str, partition: int) -> Dict[str, int]:
        """获取队列消息数量。"""
        if not self._channel:
            return {}
        try:
            queue = await self._channel.get_queue(topic)
            info = await queue.declare(passive=True)
            return {
                "low": 0,
                "high": info.message_count,
                "committed": 0,
            }
        except Exception:
            return {}
