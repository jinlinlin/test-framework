"""
Allure 报告器 — 生成 Allure 兼容的结果文件。

特点：
- 生成 Allure 标准格式的结果文件
- 可被 allure serve / allure generate 命令展示
- 支持附件、步骤、标签等 Allure 特性
"""
from __future__ import annotations

import json
import logging
import os
import uuid
import datetime
from typing import Any, Dict, List

from ..base import BaseReporter

logger = logging.getLogger(__name__)


class AllureReporter(BaseReporter):
    """
    Allure 报告器。

    生成 Allure 兼容的 JSON 结果文件，可通过 allure serve 查看。

    配置::

        AllureReporter(output_dir="./allure-results")
    """

    @property
    def reporter_type(self) -> str:
        return "allure"

    def __init__(self, output_dir: str = "./allure-results") -> None:
        """
        Args:
            output_dir: Allure 结果目录。
        """
        self._output_dir = output_dir

    async def on_test_completed(self, result: Dict[str, Any]) -> None:
        """
        将单个测试结果写入 Allure 格式文件。

        每个测试用例生成一个独立的 JSON 文件。
        """
        os.makedirs(self._output_dir, exist_ok=True)

        test_uuid = str(uuid.uuid4())
        status = result.get("status", "unknown")

        # 映射状态到 Allure 状态
        allure_status_map = {
            "passed": "passed",
            "failed": "failed",
            "error": "broken",
            "skipped": "skipped",
        }
        allure_status = allure_status_map.get(status, "unknown")

        # 构建 Allure 结果对象
        allure_result = {
            "uuid": test_uuid,
            "name": result.get("test_name", "unnamed"),
            "fullName": result.get("test_name", "unnamed"),
            "status": allure_status,
            "stage": "finished",
            "start": int(datetime.datetime.now().timestamp() * 1000),
            "stop": int(
                (datetime.datetime.now().timestamp() + result.get("duration", 0)) * 1000
            ),
            "labels": [
                {"name": "suite", "value": result.get("suite_name", "default")},
                {"name": "framework", "value": "uniplore-test-framework"},
            ],
            "parameters": [],
            "steps": [],
            "attachments": [],
        }

        # 添加错误信息
        error_msg = result.get("error_message", "")
        if error_msg:
            allure_result["statusDetails"] = {
                "message": error_msg[:200],
                "trace": error_msg,
            }

        # 添加指标作为参数
        metrics = result.get("metrics", {})
        for k, v in metrics.items():
            allure_result["parameters"].append({"name": k, "value": str(v)})

        # 写入文件
        filename = f"{test_uuid}-result.json"
        filepath = os.path.join(self._output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(allure_result, f, ensure_ascii=False, indent=2)

    async def on_plan_completed(
        self,
        plan_name: str,
        results: List[Dict[str, Any]],
    ) -> str:
        """
        生成 Allure 环境描述文件。

        Args:
            plan_name: 测试计划名称。
            results: 所有测试结果（已在 on_test_completed 中逐个处理）。

        Returns:
            Allure 结果目录路径。
        """
        os.makedirs(self._output_dir, exist_ok=True)

        # 写入 environment.properties
        env_file = os.path.join(self._output_dir, "environment.properties")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(f"Framework=uniplore-test-framework\n")
            f.write(f"Plan={plan_name}\n")
            f.write(f"Total={len(results)}\n")
            passed = sum(1 for r in results if r.get("status") == "passed")
            f.write(f"Passed={passed}\n")
            f.write(f"Failed={len(results) - passed}\n")

        # 写入 categories.json（分类配置）
        categories = [
            {
                "name": "测试失败",
                "matchedStatuses": ["failed"],
            },
            {
                "name": "系统错误",
                "matchedStatuses": ["broken"],
            },
            {
                "name": "已跳过",
                "matchedStatuses": ["skipped"],
            },
        ]
        cat_file = os.path.join(self._output_dir, "categories.json")
        with open(cat_file, "w", encoding="utf-8") as f:
            json.dump(categories, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Allure 结果已生成: {self._output_dir} "
            f"(使用 'allure serve {self._output_dir}' 查看)"
        )
        return self._output_dir
