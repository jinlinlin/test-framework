"""adapters 包 — 适配器层，屏蔽不同中间件的接口差异。"""
from .base import BaseAdapter
from .adapter_factory import AdapterFactory

__all__ = ["BaseAdapter", "AdapterFactory"]
