"""
setup.py — 框架安装配置（兼容 pip install -e . 方式安装）。

使用 pyproject.toml 作为主要构建配置，
本文件保留用于兼容旧版 pip 和 editable install。
"""
from setuptools import setup, find_packages

setup(
    name="uniplore-test-framework",
    version="1.0.0",
    description="全维度工程化测试框架 — 性能/接口/数据库/智能问答/安全测试",
    long_description=open("../README.md", encoding="utf-8").read() if __import__("os").path.exists("../README.md") else "",
    long_description_content_type="text/markdown",
    author="framework-team",
    python_requires=">=3.10",
    packages=find_packages(where=".."),
    package_dir={"": ".."},
    install_requires=[
        "httpx>=0.25.0",
        "aiohttp>=3.9.0",
        "pyyaml>=6.0",
        "pydantic>=2.0",
        "jsonschema>=4.20.0",
        "jinja2>=3.1.0",
        "playwright>=1.40.0",
        "psutil>=5.9.0",
        "structlog>=23.2.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
            "flake8>=7.0.0",
            "mypy>=1.8.0",
            "black>=24.1.0",
        ],
        "database": [
            "asyncpg>=0.29.0",
            "aiomysql>=0.2.0",
            "motor>=3.3.0",
            "redis>=5.0.0",
        ],
        "grpc": [
            "grpcio>=1.60.0",
            "grpcio-tools>=1.60.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "test-framework=test_framework.__main__:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
