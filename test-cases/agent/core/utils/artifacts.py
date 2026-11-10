"""测试产物落盘工具：按用例名分目录、时间戳前缀保存 JSON/文本产物。

原先 robust/test_agent_robust.py 自带 _save_artifact 与 paper_interpret 的
_save_full_artifacts 是两套平行实现；本模块提供最简通用入口，供直发 httpx
的横向切面用例（robust）复用，paper_interpret 的富产物保存仍走
test_paper_common._save_full_artifacts（其结构更重，暂不收敛）。
"""
import json  # 序列化 JSON 产物
from datetime import datetime  # 产物文件名时间戳
from pathlib import Path  # 产物路径处理
from typing import Any  # 类型标注


def save_artifact(output_dir: Path, case_name: str, data: Any, suffix: str = "json") -> None:
    """保存产物到 output_dir/{case_name}/{时间戳}.{suffix}。

    Args:
        output_dir: 产物根目录（test_output/）。
        case_name: 用例名（作为子目录名）。
        data: 待落盘数据（suffix=json 时 json.dumps 序列化，否则 str(data)）。
        suffix: 文件扩展名（默认 json）。
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    case_dir = output_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2) if suffix == "json" else str(data)
    (case_dir / f"{ts}.{suffix}").write_text(content, encoding="utf-8")
