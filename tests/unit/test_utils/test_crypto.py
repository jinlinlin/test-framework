# -*- coding: utf-8 -*-
"""CryptoUtils 单元测试。

测试加密工具函数（MD5、SHA、Base64）。
"""
import pytest
import base64


class TestCryptoUtils:
    """测试加密工具类。"""

    def test_md5_hash(self):
        """测试 MD5 哈希。"""
        from test_framework.utils.crypto import CryptoUtils

        crypto = CryptoUtils()
        result = crypto.md5("hello")
        assert isinstance(result, str)
        assert len(result) == 32
        # 已知值: md5("hello") = 5d41402abc4b2a76b9719d911017c592
        assert result == "5d41402abc4b2a76b9719d911017c592"

    def test_sha256_hash(self):
        """测试 SHA-256 哈希。"""
        from test_framework.utils.crypto import CryptoUtils

        crypto = CryptoUtils()
        result = crypto.sha256("hello")
        assert isinstance(result, str)
        assert len(result) == 64

    def test_base64_encode_decode(self):
        """测试 Base64 编解码往返。"""
        from test_framework.utils.crypto import CryptoUtils

        crypto = CryptoUtils()
        original = "测试中文数据"
        encoded = crypto.base64_encode(original)
        decoded = crypto.base64_decode(encoded)
        assert decoded == original

    def test_sha1_hash(self):
        """测试 SHA-1 哈希。"""
        from test_framework.utils.crypto import CryptoUtils

        crypto = CryptoUtils()
        result = crypto.sha1("test")
        assert isinstance(result, str)
        assert len(result) == 40
