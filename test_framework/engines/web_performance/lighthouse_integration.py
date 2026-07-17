"""
Lighthouse 集成 — 调用 Lighthouse CLI 执行综合性能审计。

职责：集成 Google Lighthouse，对目标 URL 执行性能、可访问性、
      最佳实践等维度的综合审计，解析并返回各类评分。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LighthouseIntegration:
    """
    Lighthouse 集成模块。

    通过调用 Lighthouse CLI 对目标 URL 执行审计，
    解析 JSON 报告提取各维度评分。

    Attributes:
        _config: Lighthouse 配置。
        _categories: 审计类别列表。
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        初始化 Lighthouse 集成。

        Args:
            config: lighthouse 配置区块。
        """
        self._config = config
        self._categories: List[str] = config.get("categories", [
            "performance", "accessibility", "best-practices", "seo"
        ])

    async def audit(
        self,
        url: str,
        categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        对目标 URL 执行 Lighthouse 审计。

        Args:
            url: 待审计的 URL。
            categories: 审计类别（默认使用配置中的类别）。

        Returns:
            审计结果字典，包含各类评分。
        """
        cats = categories or self._categories

        # 创建临时文件存放报告
        output_path = os.path.join(tempfile.gettempdir(), f"lighthouse_{os.getpid()}.json")

        try:
            # 构建 Lighthouse CLI 命令
            cmd = [
                "npx", "lighthouse", url,
                f"--output=json",
                f"--output-path={output_path}",
                "--chrome-flags=--headless",
            ]

            # 添加审计类别
            for cat in cats:
                cmd.append(f"--only-categories={cat}")

            # 执行 Lighthouse
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=120
                )
            except asyncio.TimeoutError:
                process.kill()
                logger.warning("Lighthouse 审计超时")
                return {"error": "审计超时"}

            # 解析 JSON 报告
            if os.path.exists(output_path):
                with open(output_path, "r", encoding="utf-8") as f:
                    raw_report = json.load(f)
                return self.parse_report(raw_report)
            else:
                logger.warning("Lighthouse 报告文件未生成")
                return {"error": "报告文件未生成"}

        except FileNotFoundError:
            logger.warning("Lighthouse CLI 未安装，请运行: npm install -g lighthouse")
            return {"error": "Lighthouse CLI 未安装"}
        except Exception as e:
            logger.error(f"Lighthouse 审计异常: {e}")
            return {"error": str(e)}
        finally:
            # 清理临时文件
            if os.path.exists(output_path):
                os.unlink(output_path)

    def parse_report(self, raw_report: Dict[str, Any]) -> Dict[str, float]:
        """
        从 Lighthouse 原始报告中提取各类评分。

        Args:
            raw_report: Lighthouse JSON 报告。

        Returns:
            类别名称 → 评分（0-100）的字典。
        """
        scores: Dict[str, float] = {}

        categories_data = raw_report.get("categories", {})
        for cat_id, cat_data in categories_data.items():
            # Lighthouse 评分范围 0-1，转换为 0-100
            score = cat_data.get("score", 0)
            scores[cat_id] = round(score * 100, 1)

        # 提取关键审计指标
        audits = raw_report.get("audits", {})
        key_metrics = {}
        for metric_id in ["first-contentful-paint", "largest-contentful-paint",
                          "cumulative-layout-shift", "speed-index"]:
            audit = audits.get(metric_id, {})
            key_metrics[metric_id] = {
                "score": audit.get("score", 0),
                "display_value": audit.get("displayValue", ""),
                "numeric_value": audit.get("numericValue", 0),
            }

        scores["key_metrics"] = key_metrics
        return scores
