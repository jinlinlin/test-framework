"""
Kubernetes 集成 — K8s 集群操作（创建 Job、获取日志、扩缩容、获取指标）。

职责：封装 kubernetes Python 客户端，提供异步操作接口。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class KubernetesIntegration:
    """
    Kubernetes 集成。

    使用示例::

        k8s = KubernetesIntegration(kubeconfig="~/.kube/config")
        job_id = await k8s.create_job({"apiVersion": "batch/v1", ...})
        logs = await k8s.get_pod_logs("my-pod", "default")
    """

    def __init__(self, kubeconfig: Optional[str] = None, namespace: str = "default") -> None:
        """
        初始化 K8s 集成。

        Args:
            kubeconfig: kubeconfig 文件路径（None 使用默认配置）。
            namespace: 默认命名空间。
        """
        self._kubeconfig = kubeconfig
        self._namespace = namespace
        self._client = None

    def _get_client(self) -> Any:
        """获取 kubernetes 客户端（延迟导入）。"""
        if self._client is None:
            try:
                from kubernetes import client, config
                if self._kubeconfig:
                    config.load_kube_config(config_file=self._kubeconfig)
                else:
                    try:
                        config.load_incluster_config()
                    except Exception:
                        config.load_kube_config()
                self._client = client
            except ImportError:
                raise ImportError("kubernetes 包未安装: pip install kubernetes")
        return self._client

    async def create_job(self, spec: Dict[str, Any]) -> str:
        """
        创建 K8s Job。

        Args:
            spec: Job 规范字典。

        Returns:
            创建的 Job 名称。
        """
        client = self._get_client()
        batch_v1 = client.BatchV1Api()
        name = spec.get("metadata", {}).get("name", "test-job")
        try:
            batch_v1.create_namespaced_job(namespace=self._namespace, body=spec)
            logger.info(f"K8s Job 已创建: {name}")
            return name
        except Exception as e:
            logger.error(f"创建 K8s Job 失败: {e}")
            raise

    async def get_pod_logs(self, pod_name: str, namespace: Optional[str] = None) -> str:
        """
        获取 Pod 日志。

        Args:
            pod_name: Pod 名称。
            namespace: 命名空间。

        Returns:
            日志内容字符串。
        """
        client = self._get_client()
        core_v1 = client.CoreV1Api()
        ns = namespace or self._namespace
        try:
            logs = core_v1.read_namespaced_pod_log(name=pod_name, namespace=ns)
            return logs
        except Exception as e:
            logger.error(f"获取 Pod 日志失败: {e}")
            return ""

    async def scale(self, deployment: str, replicas: int, namespace: Optional[str] = None) -> None:
        """
        调整 Deployment 副本数。

        Args:
            deployment: Deployment 名称。
            replicas: 目标副本数。
            namespace: 命名空间。
        """
        client = self._get_client()
        apps_v1 = client.AppsV1Api()
        ns = namespace or self._namespace
        try:
            body = {"spec": {"replicas": replicas}}
            apps_v1.patch_namespaced_deployment_scale(
                name=deployment, namespace=ns, body=body
            )
            logger.info(f"Deployment {deployment} 已缩放至 {replicas} 副本")
        except Exception as e:
            logger.error(f"缩放 Deployment 失败: {e}")
            raise

    async def get_metrics(self, pod_name: str, namespace: Optional[str] = None) -> Dict[str, float]:
        """
        获取 Pod 资源使用指标。

        Args:
            pod_name: Pod 名称。
            namespace: 命名空间。

        Returns:
            包含 cpu_usage / memory_usage 的字典。
        """
        client = self._get_client()
        ns = namespace or self._namespace
        try:
            custom_api = client.CustomObjectsApi()
            metrics = custom_api.get_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=ns,
                plural="pods",
                name=pod_name,
            )
            containers = metrics.get("containers", [{}])
            if containers:
                usage = containers[0].get("usage", {})
                return {
                    "cpu_usage": float(usage.get("cpu", "0").rstrip("nm")),
                    "memory_usage": float(usage.get("memory", "0").rstrip("Ki")),
                }
        except Exception as e:
            logger.debug(f"获取 Pod 指标失败: {e}")
        return {"cpu_usage": 0.0, "memory_usage": 0.0}
