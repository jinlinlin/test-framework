"""
Docker 集成 — Docker 容器操作（构建、运行、停止、日志、指标）。

职责：封装 docker Python SDK，提供异步容器管理接口。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DockerIntegration:
    """
    Docker 集成。

    使用示例::

        docker = DockerIntegration()
        container_id = await docker.run("nginx:latest", ports={"80/tcp": 8080})
        logs = await docker.logs(container_id)
        await docker.stop(container_id)
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        """
        初始化 Docker 集成。

        Args:
            base_url: Docker daemon URL（None 使用默认）。
        """
        self._base_url = base_url
        self._client = None

    def _get_client(self) -> Any:
        """获取 Docker 客户端（延迟导入）。"""
        if self._client is None:
            try:
                import docker
                if self._base_url:
                    self._client = docker.DockerClient(base_url=self._base_url)
                else:
                    self._client = docker.from_env()
            except ImportError:
                raise ImportError("docker 包未安装: pip install docker")
        return self._client

    async def build(self, dockerfile: str, tag: str, context: str = ".") -> str:
        """
        构建 Docker 镜像。

        Args:
            dockerfile: Dockerfile 路径。
            tag: 镜像标签。
            context: 构建上下文目录。

        Returns:
            镜像 ID。
        """
        client = self._get_client()
        try:
            image, build_logs = client.images.build(
                path=context, dockerfile=dockerfile, tag=tag, rm=True
            )
            logger.info(f"镜像已构建: {tag} ({image.short_id})")
            return image.short_id
        except Exception as e:
            logger.error(f"构建镜像失败: {e}")
            raise

    async def run(self, image: str, **kwargs: Any) -> str:
        """
        运行 Docker 容器。

        Args:
            image: 镜像名称。
            **kwargs: 传递给 docker.containers.run 的参数。

        Returns:
            容器 ID。
        """
        client = self._get_client()
        try:
            container = client.containers.run(image, detach=True, **kwargs)
            logger.info(f"容器已启动: {container.short_id}")
            return container.short_id
        except Exception as e:
            logger.error(f"启动容器失败: {e}")
            raise

    async def stop(self, container_id: str, timeout: int = 10) -> None:
        """
        停止并移除容器。

        Args:
            container_id: 容器 ID。
            timeout: 停止超时（秒）。
        """
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            container.stop(timeout=timeout)
            container.remove()
            logger.info(f"容器已停止并移除: {container_id}")
        except Exception as e:
            logger.error(f"停止容器失败: {e}")

    async def logs(self, container_id: str, tail: int = 100) -> str:
        """
        获取容器日志。

        Args:
            container_id: 容器 ID。
            tail: 获取最后 N 行。

        Returns:
            日志字符串。
        """
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            return container.logs(tail=tail).decode("utf-8", errors="replace")
        except Exception as e:
            logger.error(f"获取容器日志失败: {e}")
            return ""

    async def stats(self, container_id: str) -> Dict[str, float]:
        """
        获取容器资源使用指标。

        Args:
            container_id: 容器 ID。

        Returns:
            包含 cpu_percent / memory_mb / network_rx_mb / network_tx_mb 的字典。
        """
        client = self._get_client()
        try:
            container = client.containers.get(container_id)
            stats = container.stats(stream=False)

            # CPU
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"]
                - stats["precpu_stats"]["system_cpu_usage"]
            )
            num_cpus = stats["cpu_stats"].get("online_cpus", 1)
            cpu_percent = (cpu_delta / system_delta * num_cpus * 100) if system_delta > 0 else 0.0

            # Memory
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_mb = mem_usage / (1024 * 1024)

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(mem_mb, 2),
            }
        except Exception as e:
            logger.error(f"获取容器指标失败: {e}")
            return {"cpu_percent": 0.0, "memory_mb": 0.0}
