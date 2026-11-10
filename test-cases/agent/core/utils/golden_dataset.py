"""黄金评测集单一事实源：JSON 文件读取、路径归一化、样本筛选与未命中告警。

供测试用例包（paper_interpret / robust）与 Langfuse 上报侧共用，避免各处各自读取、
各自写一套匹配规则：
- read_golden_file：读取黄金集 JSON 数组，文件缺失时告警并返回 []（严格模式抛错）
- norm_pdf_path：PDF 路径归一化（相对/绝对、正反斜杠、大小写差异均可命中）
- find_golden_samples：按「PDF 归一化路径 + 问题精确」筛选样本，两侧共用的唯一匹配规则
- warn_golden_miss：未命中告警；严格模式下抛 LookupError，阻断静默回退

严格模式（GOLDEN_STRICT=true，支持 config/.env 或环境变量）：
黄金集文件缺失或样本未命中时直接失败，用于回归门禁等不允许降级到内置默认值的场景。
"""
import json  # 解析黄金集 JSON 数组
import os  # normcase 消除 Windows 大小写/斜杠差异
from pathlib import Path  # 黄金集目录路径处理
from typing import Optional  # 类型标注

from core.utils.config import PROJECT_ROOT, config  # 项目根目录与配置入口

# 黄金评测集数据目录（单一事实源路径）
GOLDEN_DIR = PROJECT_ROOT / "test_data" / "golden_dataset"


def golden_strict() -> bool:
    """严格模式开关（GOLDEN_STRICT，默认 false）：true 时黄金集缺失/未命中直接抛错。"""
    value = config.get("GOLDEN_STRICT")
    return value is not None and value.lower() == "true"


def read_golden_file(filename: str) -> list:
    """读取黄金集 JSON 数组文件。

    Args:
        filename: 黄金集文件名（如 "paper_golden_v1.json"），位于 GOLDEN_DIR 下

    Returns:
        样本列表；文件缺失时返回 []（严格模式抛 FileNotFoundError）
    """
    path = GOLDEN_DIR / filename
    if not path.is_file():
        msg = f"黄金评测集文件不存在：{path}"
        if golden_strict():
            raise FileNotFoundError(msg)
        print(f"[黄金集] 警告：{msg}，将回退到内置默认值")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def norm_pdf_path(value: Optional[str]) -> Optional[str]:
    """将 PDF 路径归一化为项目根下的规范绝对路径。

    黄金集内存相对路径（test_data/pdfs/...），而 fixture 传入绝对路径，
    不归一化会导致精确匹配永远未命中（历史上真实运行始终回退默认值）。
    """
    if not value:
        return None
    p = Path(value)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return os.path.normcase(str(p.resolve()))


def find_golden_samples(
    filename: str, pdf_path: Optional[str] = None, question: Optional[str] = None
) -> list:
    """按「PDF 路径（归一化）+ 问题（精确）」筛选黄金集样本。

    为什么要把匹配规则也抽进来：用例侧 Judge 与 Langfuse 上报侧曾各自实现一遍，
    一侧只比问题文本、一侧比归一化路径，同一次运行里报告写的锚点与 Judge 真正
    用的 expected_points 不是同一条样本（问题文本在黄金集内会跨论文重复），
    报告上的“预期要点”就变成误导。两边调同一个函数后不可能再分叉。

    不加“仅问题命中”“问题子串”这类逐级放宽的回退——放宽后匹到的样本用例侧根本
    没命中（会回退内置默认要点），报告却显示一堆 Judge 从未用过的要点。
    未命中就是未命中，由调用方按与用例侧相同的方式告警。
    """
    samples = read_golden_file(filename)
    if pdf_path:
        key = norm_pdf_path(pdf_path)
        samples = [s for s in samples if norm_pdf_path(s.get("pdf_path")) == key]
    if question:
        samples = [s for s in samples if s.get("question") == question]
    return samples


def warn_golden_miss(dataset: str, **filters) -> None:
    """黄金集未命中告警（调用方回退内置默认值前必须调用，避免静默降级）。

    Args:
        dataset: 黄金集文件名（用于日志定位）
        **filters: 未命中的筛选条件（如 pdf_path / question / category / sample_id）

    Raises:
        LookupError: 严格模式下未命中直接抛错，由调用方测试失败暴露
    """
    desc = "、".join(f"{k}={v!r}" for k, v in filters.items() if v is not None) or "无筛选条件"
    if golden_strict():
        raise LookupError(f"[黄金集] 严格模式：{dataset} 未匹配到样本（{desc}），禁止回退内置默认值")
    print(f"[黄金集] 警告：{dataset} 未匹配到样本（{desc}），回退到内置默认值")
