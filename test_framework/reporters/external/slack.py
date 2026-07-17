"""
Slack 通知器 — 发送测试报告到 Slack 频道。

特点：
- 通过 Webhook URL 发送消息
- 支持富文本格式（Block Kit）
- 包含汇总统计和失败详情
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SlackNotifier:
    """
    Slack 通知器。

    配置::

        notifier = SlackNotifier(
            webhook_url="https://hooks.slack.com/services/xxx/yyy/zzz",
            channel="#test-reports",
        )
    """

    def __init__(
        self,
        webhook_url: str = "",
        channel: str = "#test-reports",
        username: str = "测试框架",
    ) -> None:
        """
        Args:
            webhook_url: Slack Incoming Webhook URL。
            channel: 目标频道。
            username: 发送者名称。
        """
        self._webhook_url = webhook_url
        self._channel = channel
        self._username = username

    async def notify(
        self,
        plan_name: str,
        results: List[Dict[str, Any]],
        webhook_url: str = "",
    ) -> None:
        """
        发送测试报告到 Slack。

        Args:
            plan_name: 测试计划名称。
            results: 测试结果列表。
            webhook_url: 覆盖默认 Webhook URL。
        """
        import aiohttp

        url = webhook_url or self._webhook_url
        if not url:
            logger.warning("Slack Webhook URL 未配置，跳过通知")
            return

        # 计算汇总
        total = len(results)
        passed = sum(1 for r in results if r.get("status") == "passed")
        failed = sum(1 for r in results if r.get("status") == "failed")
        errors = sum(1 for r in results if r.get("status") == "error")
        pass_rate = (passed / total * 100) if total > 0 else 0

        # 构建 Slack Block Kit 消息
        emoji = ":white_check_mark:" if (failed + errors == 0) else ":x:"
        color = "#36a64f" if (failed + errors == 0) else "#dc3545"

        # 失败用例列表
        failed_items = ""
        for r in results:
            if r.get("status") in ("failed", "error"):
                name = r.get("test_name", "")
                err = r.get("error_message", "")[:100]
                failed_items += f"• `{name}`: {err}\n"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{emoji} 测试报告: {plan_name}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*总计:* {total}"},
                    {"type": "mrkdwn", "text": f"*通过:* {passed}"},
                    {"type": "mrkdwn", "text": f"*失败:* {failed}"},
                    {"type": "mrkdwn", "text": f"*通过率:* {pass_rate:.1f}%"},
                ],
            },
        ]

        if failed_items:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*失败详情:*\n{failed_items[:500]}"},
            })

        payload = {
            "channel": self._channel,
            "username": self._username,
            "blocks": blocks,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Slack 通知发送失败 ({resp.status}): {text}")
                else:
                    logger.info(f"Slack 通知已发送到 {self._channel}")
