"""Layer 3 聚合子包：跨引擎 summary.json 消费与总览产出。"""
from .cross_engine import (
    aggregate,
    render_console,
    scan_summaries,
    write_aggregate,
)

__all__ = ["aggregate", "render_console", "scan_summaries", "write_aggregate"]
