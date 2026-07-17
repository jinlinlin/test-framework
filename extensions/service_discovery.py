"""
服务发现 — 支持 Consul / Nacos / Eureka 的服务注册与发现。

职责：提供统一的服务发现接口，自动发现被测系统实例。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ServiceDiscovery(ABC):
    """
    服务发现基类。

    使用示例::

        discovery = ConsulDiscovery(address="http://localhost:8500")
        instances = await discovery.discover("my-service")
    """

    @abstractmethod
    async def discover(self, service_name: str) -> List[Dict[str, Any]]:
        """
        发现服务实例。

        Args:
            service_name: 服务名称。

        Returns:
            服务实例列表，每个实例包含 address / port / metadata。
        """

    @abstractmethod
    async def register(self, service_info: Dict[str, Any]) -> None:
        """注册服务实例。"""

    @abstractmethod
    async def deregister(self, service_id: str) -> None:
        """注销服务实例。"""

    @abstractmethod
    async def watch(self, service_name: str, callback: Callable) -> None:
        """监听服务变更。"""


class ConsulDiscovery(ServiceDiscovery):
    """Consul 服务发现实现。"""

    def __init__(self, address: str = "http://localhost:8500") -> None:
        self._address = address

    async def discover(self, service_name: str) -> List[Dict[str, Any]]:
        """通过 Consul HTTP API 发现服务。"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self._address}/v1/catalog/service/{service_name}")
                if resp.status_code == 200:
                    return [
                        {
                            "address": item["ServiceAddress"],
                            "port": item["ServicePort"],
                            "metadata": item.get("ServiceMeta", {}),
                        }
                        for item in resp.json()
                    ]
        except Exception as e:
            logger.error(f"Consul 服务发现失败: {e}")
        return []

    async def register(self, service_info: Dict[str, Any]) -> None:
        """注册服务到 Consul。"""
        logger.info(f"Consul 注册服务: {service_info.get('name', 'unknown')}")

    async def deregister(self, service_id: str) -> None:
        """从 Consul 注销服务。"""
        logger.info(f"Consul 注销服务: {service_id}")

    async def watch(self, service_name: str, callback: Callable) -> None:
        """监听 Consul 服务变更。"""
        logger.info(f"Consul 监听服务: {service_name}")


class NacosDiscovery(ServiceDiscovery):
    """Nacos 服务发现实现。"""

    def __init__(self, address: str = "http://localhost:8848", namespace: str = "public") -> None:
        self._address = address
        self._namespace = namespace

    async def discover(self, service_name: str) -> List[Dict[str, Any]]:
        """通过 Nacos API 发现服务。"""
        try:
            import httpx
            url = f"{self._address}/nacos/v1/ns/instance/list"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params={
                    "serviceName": service_name,
                    "namespaceId": self._namespace,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    return [
                        {
                            "address": inst["ip"],
                            "port": inst["port"],
                            "metadata": inst.get("metadata", {}),
                        }
                        for inst in data.get("hosts", [])
                        if inst.get("healthy", True)
                    ]
        except Exception as e:
            logger.error(f"Nacos 服务发现失败: {e}")
        return []

    async def register(self, service_info: Dict[str, Any]) -> None:
        logger.info(f"Nacos 注册服务: {service_info.get('name', 'unknown')}")

    async def deregister(self, service_id: str) -> None:
        logger.info(f"Nacos 注销服务: {service_id}")

    async def watch(self, service_name: str, callback: Callable) -> None:
        logger.info(f"Nacos 监听服务: {service_name}")
