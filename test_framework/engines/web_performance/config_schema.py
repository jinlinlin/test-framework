"""
网页性能测试配置 Schema 定义。

定义网页性能测试引擎的配置验证规则。
"""

# 网页性能测试引擎的配置 Schema
WEB_PERFORMANCE_SCHEMA = {
    "type": "object",
    "description": "网页性能测试引擎配置",
    "properties": {
        "browser": {
            "type": "string",
            "description": "浏览器类型",
            "enum": ["chromium", "firefox", "webkit"],
            "default": "chromium",
        },
        "headless": {
            "type": "boolean",
            "description": "是否无头模式",
            "default": True,
        },
        "timeout": {
            "type": "integer",
            "description": "页面加载超时（毫秒）",
            "minimum": 1000,
            "default": 30000,
        },
        "viewport": {
            "type": "object",
            "description": "视口大小",
            "properties": {
                "width": {"type": "integer", "minimum": 320, "default": 1920},
                "height": {"type": "integer", "minimum": 240, "default": 1080},
            },
        },
        "lighthouse": {
            "type": "object",
            "description": "Lighthouse 集成配置",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "web_vitals": {
            "type": "object",
            "description": "Web Vitals 配置",
            "properties": {
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "thresholds": {"type": "object"},
            },
        },
        "resource_monitor": {
            "type": "object",
            "description": "资源监控配置",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "track_js": {"type": "boolean"},
                "track_css": {"type": "boolean"},
                "track_images": {"type": "boolean"},
                "track_fonts": {"type": "boolean"},
                "track_api_calls": {"type": "boolean"},
            },
        },
    },
}
