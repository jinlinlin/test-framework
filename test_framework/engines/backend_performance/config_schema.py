"""
后端性能测试配置 Schema 定义。

定义后端性能测试引擎的配置验证规则。
"""

BACKEND_PERFORMANCE_SCHEMA = {
    "type": "object",
    "description": "后端性能测试引擎配置",
    "properties": {
        "protocol": {
            "type": "string",
            "description": "协议类型",
            "enum": ["http", "grpc", "websocket"],
            "default": "http",
        },
        "concurrency": {
            "type": "integer",
            "description": "并发数",
            "minimum": 1,
            "default": 100,
        },
        "duration": {
            "type": "integer",
            "description": "测试持续时间（秒）",
            "minimum": 1,
            "default": 300,
        },
        "ramp_up": {
            "type": "integer",
            "description": "预热时间（秒）",
            "minimum": 0,
            "default": 30,
        },
        "load_profile": {
            "type": "string",
            "description": "负载模型",
            "enum": ["constant", "step", "spike", "soak"],
            "default": "constant",
        },
        "http": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                "headers": {"type": "object"},
                "body": {},
                "timeout": {"type": "integer", "minimum": 1},
            },
        },
        "grpc": {
            "type": "object",
            "properties": {
                "proto_file": {"type": "string"},
                "service": {"type": "string"},
                "method": {"type": "string"},
                "metadata": {"type": "object"},
            },
        },
        "resource_monitoring": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "interval": {"type": "integer", "minimum": 1, "default": 5},
                "targets": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "thresholds": {
            "type": "object",
            "properties": {
                "response_time_p50": {"type": "integer", "minimum": 1},
                "response_time_p95": {"type": "integer", "minimum": 1},
                "response_time_p99": {"type": "integer", "minimum": 1},
                "error_rate": {"type": "number", "minimum": 0, "maximum": 1},
                "throughput_min": {"type": "integer", "minimum": 1},
            },
        },
    },
}
