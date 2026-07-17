"""
test_framework 包 — 全维度工程化测试框架主入口。

本框架是一套工程化、模块化、配置驱动、多语言协同的全场景自动化测试框架，
统一支撑性能测试、接口测试、数据库测试、智能问答测试、安全测试等全类型测试能力。

核心能力：
    - 网页性能测试（Playwright + Lighthouse）
    - 后端性能测试（HTTP/gRPC 负载施压）
    - REST API 测试（Python/Node.js 双引擎）
    - 数据库性能测试（MySQL/PostgreSQL/MongoDB/Redis）
    - 知识库问答测试（RAG 评测）
    - 渗透测试（SQL注入/XSS/路径遍历/命令注入/SSRF/XXE）
    - 越权访问测试（角色提升/会话固定/Token重放/JWT/OAuth/IDOR）

技术栈：
    - Python（核心主框架）
    - Node.js（高性能辅助引擎）
    - Shell（工程运维层）

版本：1.0.0
"""

__version__ = "1.0.0"
__author__ = "framework-team"
