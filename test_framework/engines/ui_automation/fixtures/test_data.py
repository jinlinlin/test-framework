"""
测试数据。

包含通用测试数据。
"""
from __future__ import annotations

test_users = {
    "admin": {
        "username": "admin",
        "password": "admin123",
        "email": "admin@example.com",
        "role": "admin",
    },
    "user": {
        "username": "testuser",
        "password": "password123",
        "email": "testuser@example.com",
        "role": "user",
    },
}

test_credentials = {
    "api_key": "test-api-key-12345",
}

test_products = {
    "product_1": {
        "id": "prod-001",
        "name": "Test Product",
        "price": 99.99,
        "category": "Test",
    },
}