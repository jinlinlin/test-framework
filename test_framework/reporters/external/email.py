"""
Email 报告器 — 发送测试报告邮件。

特点：
- 通过 SMTP 发送邮件
- 支持 HTML 邮件正文
- 支持附件（如 HTML/JSON 报告文件）
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EmailReporter:
    """
    Email 报告器。

    配置::

        reporter = EmailReporter()
        await reporter.send(
            report_content="<html>...</html>",
            recipients=["dev@example.com"],
            smtp_config={
                "host": "smtp.example.com",
                "port": 587,
                "username": "test@example.com",
                "password": "xxx",
                "use_tls": True,
            },
        )
    """

    async def send(
        self,
        report_content: str,
        recipients: List[str],
        smtp_config: Dict[str, Any],
        subject: str = "测试报告",
        attachments: Optional[List[str]] = None,
    ) -> None:
        """
        发送测试报告邮件。

        Args:
            report_content: HTML 格式的报告内容。
            recipients: 收件人邮箱列表。
            smtp_config: SMTP 配置。
            subject: 邮件主题。
            attachments: 附件文件路径列表。
        """
        import asyncio

        host = smtp_config.get("host", "localhost")
        port = smtp_config.get("port", 587)
        username = smtp_config.get("username", "")
        password = smtp_config.get("password", "")
        use_tls = smtp_config.get("use_tls", True)
        sender = smtp_config.get("sender", username)

        # 构建邮件
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        # HTML 正文
        msg.attach(MIMEText(report_content, "html", "utf-8"))

        # 添加附件
        if attachments:
            for filepath in attachments:
                try:
                    with open(filepath, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        import os
                        filename = os.path.basename(filepath)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={filename}",
                        )
                        msg.attach(part)
                except Exception as e:
                    logger.warning(f"添加附件失败 {filepath}: {e}")

        # 发送（在线程池中执行以避免阻塞）
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._send_email,
            host, port, username, password, use_tls, msg, recipients,
        )

    def _send_email(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool,
        msg: MIMEMultipart,
        recipients: List[str],
    ) -> None:
        """同步发送邮件。"""
        try:
            if use_tls:
                server = smtplib.SMTP(host, port)
                server.starttls()
            else:
                server = smtplib.SMTP(host, port)

            if username:
                server.login(username, password)

            server.sendmail(msg["From"], recipients, msg.as_string())
            server.quit()
            logger.info(f"测试报告邮件已发送到: {', '.join(recipients)}")
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            raise
