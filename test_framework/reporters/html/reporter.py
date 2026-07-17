"""
HTML 报告器 — 生成独立可浏览的 HTML 测试报告。

特点：
- 使用 Jinja2 模板引擎渲染
- 内联 CSS/JS，单文件可独立打开
- 包含概览、详细结果、安全专项报告
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

from ..base import BaseReporter

logger = logging.getLogger(__name__)


class HTMLReporter(BaseReporter):
    """
    HTML 报告器。

    配置::

        HTMLReporter(
            output_dir="./reports/html",
            template_dir=None,  # 使用内置模板
        )
    """

    @property
    def reporter_type(self) -> str:
        return "html"

    def __init__(
        self,
        output_dir: str = "./reports/html",
        template_dir: Optional[str] = None,
    ) -> None:
        """
        Args:
            output_dir: HTML 报告输出目录。
            template_dir: 自定义模板目录（None 使用内置模板）。
        """
        self._output_dir = output_dir
        self._template_dir = template_dir
        self._test_results: List[Dict[str, Any]] = []

    async def on_test_completed(self, result: Dict[str, Any]) -> None:
        """收集每个测试结果。"""
        self._test_results.append(result)

    async def on_plan_completed(
        self,
        plan_name: str,
        results: List[Dict[str, Any]],
    ) -> str:
        """
        生成 HTML 报告。

        Args:
            plan_name: 测试计划名称。
            results: 所有测试结果。

        Returns:
            HTML 报告文件路径。
        """
        os.makedirs(self._output_dir, exist_ok=True)

        # 计算汇总统计
        total = len(results)
        passed = sum(1 for r in results if r.get("status") == "passed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        errors = sum(1 for r in results if r.get("status") == "error")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        pass_rate = (passed / total * 100) if total > 0 else 0
        total_duration = sum(r.get("duration", 0) for r in results)

        # 使用模板渲染
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            template_path = self._template_dir or os.path.join(os.path.dirname(__file__), "templates")
            env = Environment(
                loader=FileSystemLoader(template_path),
                autoescape=select_autoescape(["html"]),
            )
            template = env.get_template("base.html")
            html_content = template.render(
                plan_name=plan_name,
                total=total,
                passed=passed,
                failed=failed,
                errors=errors,
                skipped=skipped,
                pass_rate=f"{pass_rate:.1f}",
                total_duration=f"{total_duration:.2f}",
                results=results,
                generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        except ImportError:
            # Jinja2 不可用时，使用简单内联模板
            html_content = self._render_simple_html(
                plan_name, total, passed, failed, errors, skipped,
                pass_rate, total_duration, results,
            )

        # 写入文件
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.html"
        filepath = os.path.join(self._output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        self._test_results.clear()
        return filepath

    def _render_simple_html(
        self,
        plan_name: str,
        total: int,
        passed: int,
        failed: int,
        errors: int,
        skipped: int,
        pass_rate: float,
        total_duration: float,
        results: List[Dict[str, Any]],
    ) -> str:
        """生成简单内联 HTML（Jinja2 不可用时的降级方案）。"""
        rows = ""
        for r in results:
            status = r.get("status", "unknown")
            status_class = {
                "passed": "color:green", "failed": "color:red",
                "error": "color:orange", "skipped": "color:gray",
            }.get(status, "")
            rows += f"""
            <tr>
                <td>{r.get('test_name', '')}</td>
                <td style="{status_class}">{status}</td>
                <td>{r.get('duration', 0):.3f}s</td>
                <td>{r.get('error_message', '')}</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>测试报告 - {plan_name}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .card {{ flex: 1; padding: 20px; border-radius: 8px; text-align: center; }}
        .card h3 {{ margin: 0; font-size: 2em; }}
        .card p {{ margin: 5px 0 0; color: #666; }}
        .card.total {{ background: #e3f2fd; }} .card.total h3 {{ color: #1565c0; }}
        .card.pass {{ background: #e8f5e9; }} .card.pass h3 {{ color: #2e7d32; }}
        .card.fail {{ background: #ffebee; }} .card.fail h3 {{ color: #c62828; }}
        .card.rate {{ background: #fff3e0; }} .card.rate h3 {{ color: #e65100; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f5f5f5; font-weight: 600; }}
        tr:hover {{ background: #f9f9f9; }}
        .footer {{ margin-top: 20px; color: #999; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>测试报告: {plan_name}</h1>
        <div class="summary">
            <div class="card total"><h3>{total}</h3><p>总用例数</p></div>
            <div class="card pass"><h3>{passed}</h3><p>通过</p></div>
            <div class="card fail"><h3>{failed + errors}</h3><p>失败/错误</p></div>
            <div class="card rate"><h3>{pass_rate:.1f}%</h3><p>通过率</p></div>
        </div>
        <p>总耗时: {total_duration:.2f}s | 跳过: {skipped}</p>
        <table>
            <thead><tr><th>测试用例</th><th>状态</th><th>耗时</th><th>错误信息</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
        <div class="footer">生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>
</body>
</html>"""
        return html
