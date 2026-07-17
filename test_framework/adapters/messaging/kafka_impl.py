"""
基于 aiokafka 的 Kafka 异步适配器。

特点：
- 纯异步 Kafka 生产者和消费者
- 支持分区路由、消费者组、偏移量管理
- 支持批量发送和消息头
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .adapter import Message, MessageHandler, MessagingAdapter, TopicInfo

logger = logging.getLogger(__name__)


class KafkaAdapter(MessagingAdapter):
    """
    Kafka 异步适配器。

    配置项::

        {
            "bootstrap_servers": "localhost:9092",
            "producer_config": {
                "acks": "all",
                "retries": 3,
            },
            "consumer_config": {
                "auto_offset_reset": "earliest",
                "enable_auto_commit": True,
            },
        }
    """

    @property
    def implementation_name(self) -> str:
        return "kafka"

    def __init__(self) -> None:
        """初始化 Kafka 适配器。"""
        self._producer: Optional[Any] = None  # AIOKafkaProducer
        self._consumer: Optional[Any] = None  # AIOKafkaConsumer
        self._bootstrap_servers: str = "localhost:9092"

    async def connect(self, config: Dict[str, Any]) -> None:
        """
        创建 Kafka 生产者。

        Args:
            config: Kafka 连接配置。
        """
        from aiokafka import AIOKafkaProducer

        self._bootstrap_servers = config.get("bootstrap_servers", "localhost:9092")
        producer_config = config.get("producer_config", {})

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            acks=producer_config.get("acks", "all"),
            retries=producer_config.get("retries", 3),
            max_batch_size=producer_config.get("max_batch_size", 16384),
            linger_ms=producer_config.get("linger_ms", 10),
            compression_type=producer_config.get("compression_type", None),
        )
        await self._producer.start()
        logger.debug(f"KafkaAdapter 生产者已连接: {self._bootstrap_servers}")

    async def disconnect(self) -> None:
        """关闭生产者和消费者。"""
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
        if self._producer:
            await self._producer.stop()
            self._producer = None
        logger.debug("KafkaAdapter 已断开")

    async def is_connected(self) -> bool:
        return self._producer is not None

    # ===== 消息发布 =====

    async def publish(
        self,
        topic: str,
        value: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        if not self._producer:
            raise RuntimeError("KafkaAdapter 未连接")

        # 序列化消息
        if isinstance(value, dict):
            value_bytes = json.dumps(value, ensure_ascii=False).encode("utf-8")
        elif isinstance(value, str):
            value_bytes = value.encode("utf-8")
        elif isinstance(value, bytes):
            value_bytes = value
        else:
            value_bytes = str(value).encode("utf-8")

        key_bytes = key.encode("utf-8") if key else None
        header_list = [(k, v.encode("utf-8")) for k, v in (headers or {}).items()]

        await self._producer.send_and_wait(
            topic=topic,
            value=value_bytes,
            key=key_bytes,
            headers=header_list if header_list else None,
        )

    async def publish_batch(
        self,
        topic: str,
        messages: List[Dict[str, Any]],
    ) -> int:
        if not self._producer:
            raise RuntimeError("KafkaAdapter 未连接")

        count = 0
        batch = self._producer.create_batch()
        for msg in messages:
            value = msg.get("value", "")
            if isinstance(value, dict):
                value_bytes = json.dumps(value, ensure_ascii=False).encode("utf-8")
            else:
                value_bytes = str(value).encode("utf-8")

            key_bytes = msg.get("key")
            if key_bytes:
                key_bytes = key_bytes.encode("utf-8")

            # 逐条发送（简化实现）
            await self._producer.send_and_wait(
                topic=topic,
                value=value_bytes,
                key=key_bytes,
            )
            count += 1
        return count

    # ===== 消息消费 =====

    async def subscribe(self, topics: List[str], group_id: str = "") -> None:
        from aiokafka import AIOKafkaConsumer

        consumer_config = {
            "bootstrap_servers": self._bootstrap_servers,
            "group_id": group_id or "test_framework_group",
            "auto_offset_reset": "earliest",
        }
        self._consumer = AIOKafkaConsumer(*topics, **consumer_config)
        await self._consumer.start()
        logger.debug(f"KafkaAdapter 已订阅: {topics}")

    async def consume(
        self,
        max_messages: int = 100,
        timeout: float = 10.0,
    ) -> List[Message]:
        if not self._consumer:
            raise RuntimeError("未订阅任何主题")

        messages: List[Message] = []
        try:
            async for record in self._consumer:
                headers_dict = {}
                if record.headers:
                    headers_dict = {
                        k: v.decode("utf-8") if isinstance(v, bytes) else str(v)
                        for k, v in record.headers
                    }
                msg = Message(
                    topic=record.topic,
                    key=record.key.decode("utf-8") if record.key else None,
                    value=record.value.decode("utf-8") if record.value else None,
                    headers=headers_dict,
                    partition=record.partition,
                    offset=record.offset,
                    timestamp=record.timestamp / 1000.0 if record.timestamp else 0.0,
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
        if not self._consumer:
            raise RuntimeError("未订阅任何主题")

        count = 0
        async for record in self._consumer:
            msg = Message(
                topic=record.topic,
                key=record.key.decode("utf-8") if record.key else None,
                value=record.value.decode("utf-8") if record.value else None,
                partition=record.partition,
                offset=record.offset,
                timestamp=record.timestamp / 1000.0 if record.timestamp else 0.0,
            )
            await handler(msg)
            count += 1
            if max_messages > 0 and count >= max_messages:
                break

    async def unsubscribe(self) -> None:
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None

    # ===== 主题管理 =====

    async def create_topic(
        self,
        topic: str,
        partitions: int = 1,
        replication_factor: int = 1,
        config: Optional[Dict[str, str]] = None,
    ) -> None:
        """通过 kafka-python 的管理客户端创建主题。"""
        try:
            from kafka.admin import KafkaAdminClient, NewTopic

            admin = KafkaAdminClient(bootstrap_servers=self._bootstrap_servers)
            new_topic = NewTopic(
                name=topic,
                num_partitions=partitions,
                replication_factor=replication_factor,
                topic_configs=config or {},
            )
            admin.create_topics([new_topic])
            admin.close()
            logger.debug(f"主题已创建: {topic}")
        except ImportError:
            logger.warning("kafka-python 未安装，无法创建主题")
        except Exception as e:
            logger.warning(f"创建主题失败: {e}")

    async def delete_topic(self, topic: str) -> None:
        try:
            from kafka.admin import KafkaAdminClient

            admin = KafkaAdminClient(bootstrap_servers=self._bootstrap_servers)
            admin.delete_topics([topic])
            admin.close()
        except Exception as e:
            logger.warning(f"删除主题失败: {e}")

    async def list_topics(self) -> List[TopicInfo]:
        try:
            from kafka.admin import KafkaAdminClient

            admin = KafkaAdminClient(bootstrap_servers=self._bootstrap_servers)
            topics = admin.list_topics()
            result = [TopicInfo(name=t) for t in topics]
            admin.close()
            return result
        except Exception as e:
            logger.warning(f"列出主题失败: {e}")
            return []

    # ===== 偏移量管理 =====

    async def commit_offset(self, topic: str, partition: int, offset: int) -> None:
        if self._consumer:
            from aiokafka.structs import TopicPartition
            tp = TopicPartition(topic, partition)
            await self._consumer.commit({tp: offset})

    async def get_offset(self, topic: str, partition: int) -> Dict[str, int]:
        if not self._consumer:
            return {}
        from aiokafka.structs import TopicPartition
        tp = TopicPartition(topic, partition)
        offsets = await self._consumer.beginning_offsets([tp])
        end_offsets = await self._consumer.end_offsets([tp])
        return {
            "low": offsets.get(tp, 0),
            "high": end_offsets.get(tp, 0),
            "committed": 0,  # 需要额外查询
        }
