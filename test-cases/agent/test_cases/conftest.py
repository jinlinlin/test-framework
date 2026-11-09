"""test_cases 包级共享 fixtures：PDF 素材路径（paper_interpret 与 robust 共用）。

原先 pdf_path 的解析逻辑在 test_paper_common.py（pdf_path/pdf_path_2 两份，仅 env 键名不同）
与 robust/test_agent_robust.py（独立一份）共三处重复实现，现收敛到
core/utils/config.py 的 resolve_pdf_path() + 本文件的两个 fixture。
"""
import pytest

from core.utils.config import resolve_pdf_path  # PDF 路径归一化与存在性校验（单一实现）


@pytest.fixture(scope="session")
def pdf_path() -> str:
    """测试论文 PDF 路径（session 级，PDF_PATH 配置）：未配置或文件缺失则跳过用例。"""
    resolved = resolve_pdf_path("PDF_PATH")
    if not resolved:
        pytest.skip("未配置 PDF_PATH 或文件不存在：Agent 行为测试需要真实 PDF，请填写 config/.env。")
    return resolved


@pytest.fixture(scope="session")
def pdf_path_2() -> str:
    """第二份测试论文 PDF 路径（session 级，PDF_PATH_2 配置，应与第一份领域不同）。"""
    resolved = resolve_pdf_path("PDF_PATH_2")
    if not resolved:
        pytest.skip("未配置 PDF_PATH_2 或文件不存在：追问上传新文件用例需要第二份 PDF，请填写 config/.env。")
    return resolved
