"""环境配置模块：读取 config/.env + environments.yaml，向测试代码提供统一、带中文报错的配置入口。

环境切换机制（优先级从高到低，实测仅下列三条，并无对应的 pytest 命令行参数）：
1. 环境变量 TEST_ENV（PowerShell: $env:TEST_ENV="pre"；load_dotenv 不覆盖已存在的系统环境变量，故它高于 .env）
2. config/.env 中的 TEST_ENV 配置项
3. config/environments.yaml 中的 default_env（写成 ${TEST_ENV:-prod} 时取字面默认值 prod）

另可在用例/脚本内调 config.switch_env("pre") 运行时切换（需环境已在 environments.yaml 定义）。
"""
import os  # 读取进程环境变量
from pathlib import Path  # 跨平台路径处理
from typing import Optional  # 可选类型标注

import yaml  # 读取 environments.yaml
from dotenv import load_dotenv  # 从 .env 文件加载环境变量

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # agent-test 项目根目录（core/utils/ 的上一级）
ENV_FILE = PROJECT_ROOT / "config" / ".env"  # 机密配置文件（由 config/.env.example 复制，不入库）
ENVIRONMENTS_FILE = PROJECT_ROOT / "config" / "environments.yaml"  # 环境配置（可入库）

load_dotenv(ENV_FILE)  # 加载 .env 到环境变量；已存在的系统环境变量优先（不覆盖）

DEFAULT_AUTHORIZATION = "Basic Mzp1bmlwbG9yZS1zZXJ2ZXItcmVzZWFyY2g="  # 客户端 Basic 认证默认值：Base64(clientID:clientSecret)，与仓库根 README 的 config.yml 示例（uniplore-server-research 客户端）一致


def _load_environments() -> dict:
    """加载 environments.yaml 配置。"""
    if not ENVIRONMENTS_FILE.exists():
        return {}
    with open(ENVIRONMENTS_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_env_name() -> str:
    """解析当前环境名称（优先级：环境变量 > .env > 默认值）。"""
    # 优先级 1：环境变量 TEST_ENV（运行时设置）
    env_name = os.getenv("TEST_ENV")
    if env_name:
        return env_name.strip()
    # 优先级 2：.env 中的 TEST_ENV（已随 load_dotenv 加载到环境变量）
    # 优先级 3：environments.yaml 中的 default_env
    env_config = _load_environments()
    default = env_config.get("default_env", "prod")
    # 处理 ${TEST_ENV:-prod} 格式
    if default.startswith("${"):
        return "prod"
    return default


class ConfigError(RuntimeError):
    """配置缺失/非法时抛出的异常，报错信息为中文并给出修复指引。"""


class Config:
    """全局配置对象：惰性读取环境变量，必填项缺失时抛出中文 ConfigError。
    
    支持环境切换：通过 TEST_ENV 环境变量或 config/.env 中的 TEST_ENV 配置项切换环境。
    """

    def __init__(self) -> None:
        self._runtime_token: Optional[str] = None  # 运行时注入的 token（登录/续期后覆盖）
        self._env_config = _load_environments()  # 加载 environments.yaml
        self._current_env = _resolve_env_name()  # 当前环境名称

    def set_runtime_token(self, token: str) -> None:
        """运行时注入 token（登录成功或续期后调用），同时更新环境变量和 .env 文件。"""
        self._runtime_token = token
        import os
        os.environ["TOKEN"] = token  # 同步环境变量，确保后续 get("TOKEN") 也能读到

    def get(self, key: str) -> Optional[str]:
        """读取可选环境变量：未设置或空白返回 None，否则返回去空白后的值。"""
        value = os.getenv(key)  # 读取环境变量
        if value is None or not value.strip():  # 未设置或纯空白视为缺失
            return None
        return value.strip()  # 返回去首尾空白后的值

    def require(self, key: str, hint: str) -> str:
        """读取必填环境变量：缺失时抛出带获取指引的中文 ConfigError。"""
        value = self.get(key)  # 先按可选方式读取
        if value is None:  # 缺失则抛出中文错误
            raise ConfigError(
                f"缺少必填环境变量 {key}：{hint}。"
                f"请复制 config/.env.example 为 config/.env 后填写。"
            )
        return value

    @property
    def base_url(self) -> str:
        """应用网关基础地址（前端 apiURL），根据 TEST_ENV 自动切换环境。
        
        优先级：
        1. BASE_URL 环境变量（手动覆盖）
        2. environments.yaml 中当前环境的 base_url
        """
        # 优先级 1：手动配置的 BASE_URL（向后兼容）
        manual_url = self.get("BASE_URL")
        if manual_url:
            return manual_url.rstrip("/")
        
        # 优先级 2：从 environments.yaml 读取当前环境的 base_url
        envs = self._env_config.get("environments", {})
        env_config = envs.get(self._current_env, {})
        base_url = env_config.get("base_url")
        
        if not base_url:
            raise ConfigError(
                f"环境 '{self._current_env}' 未配置 base_url。"
                f"请在 config/environments.yaml 中添加，或在 config/.env 中设置 BASE_URL。"
            )
        
        return base_url.rstrip("/")

    @property
    def token(self) -> str:
        """登录态 token：优先使用运行时注入值（登录/续期后），否则读环境变量。"""
        if self._runtime_token:
            return self._runtime_token
        return self.require(
            "TOKEN", "登录态 token，浏览器登录后从开发者工具 Network 面板的 Uniplore-Auth 请求头复制"
        )

    @property
    def authorization(self) -> str:
        """客户端 Basic 认证头：可用环境变量 AUTHORIZATION 覆盖，默认用已知客户端凭据。"""
        return self.get("AUTHORIZATION") or DEFAULT_AUTHORIZATION  # 未配置时回退默认值

    @property
    def dataset_id(self) -> str:
        """知识库 ID（rag 用例必填）：知识库页面 URL 或接口响应中的 datasetId。"""
        return self.require(
            "DATASET_ID", "知识库 ID，知识库页面 URL 或对话列表接口响应中的 datasetId"
        )

    @property
    def refresh_token(self) -> Optional[str]:
        """刷新令牌（可选）：配置后自动续期 TOKEN，无需重复拖滑块登录。"""
        return self.get("REFRESH_TOKEN")

    @property
    def cleanup_after_test(self) -> bool:
        """测试后是否清理线上数据（默认 false 保留）。"""
        value = self.get("CLEANUP_AFTER_TEST")
        return value is not None and value.lower() == "true"

    @property
    def model_name(self) -> Optional[str]:
        """运行模型名称（可选）：格式为**裸模型名（不带渠道前缀）**，如 qwen3.7-plus；渠道由后端按模型名自行解析，可用清单见 GET /dashboard/user/models。未配置时由该接口自动获取。"""
        return self.get("MODEL_NAME")

    @property
    def judge_base_url(self) -> Optional[str]:
        """Judge 评审模型服务地址（可选，未配置时 Judge 功能跳过）。"""
        return self.get("JUDGE_BASE_URL")

    @property
    def judge_api_key(self) -> Optional[str]:
        """Judge 评审模型 API Key（可选，未配置时 Judge 功能跳过）。"""
        return self.get("JUDGE_API_KEY")

    @property
    def judge_model(self) -> Optional[str]:
        """Judge 评审模型名称（可选，未配置时 Judge 功能跳过）。"""
        return self.get("JUDGE_MODEL")

    @property
    def judge_temperature(self) -> Optional[float]:
        """Judge 采样温度：未配置默认 0.1；显式留空或配 none/off 返回 None（请求不传该参数）。

        直接读原始环境变量以区分"未配置"与"显式留空"（get() 会把两者都归为 None，
        无法表达"留空=不传"）。kimi-k3 等推理模型不支持 temperature 参数（DashScope
        返回 HTTP 400 InvalidParameter），此类模型须配 none。取值契约见
        test_derivation_offline.py 的 TestJudgeTemperatureParsing。
        """
        raw = os.getenv("JUDGE_TEMPERATURE")
        if raw is None:
            return 0.1  # 未配置 → 默认低采样
        value = raw.strip()
        if not value or value.lower() in ("none", "off"):
            return None  # 显式留空 / none / off → 请求不传该参数
        try:
            return float(value)
        except ValueError:
            raise ConfigError(
                f"JUDGE_TEMPERATURE 配置非法：{value}（应为数值，或 none 表示不传该参数）"
            )

    @property
    def judge_gate(self) -> bool:
        """Judge 质量门禁开关（默认 false）：true 时 Judge 平均分低于及格线将导致用例失败（硬门禁）。"""
        value = self.get("JUDGE_GATE")
        return value is not None and value.lower() == "true"

    @property
    def current_env(self) -> str:
        """当前环境名称（dev/test/pre/prod）。"""
        return self._current_env
    
    @property
    def env_description(self) -> str:
        """当前环境描述。"""
        envs = self._env_config.get("environments", {})
        env_config = envs.get(self._current_env, {})
        return env_config.get("description", self._current_env)
    
    def switch_env(self, env_name: str) -> None:
        """运行时切换环境（用于测试或动态切换）。
        
        Args:
            env_name: 环境名称（dev/test/pre/prod）
        """
        envs = self._env_config.get("environments", {})
        if env_name not in envs:
            raise ConfigError(
                f"未知环境 '{env_name}'。可用环境：{', '.join(envs.keys())}"
            )
        self._current_env = env_name
        print(f"[环境切换] 已切换到 {env_name}（{envs[env_name].get('description', '')}）")
    
    @property
    def use_deepeval(self) -> bool:
        """是否使用 DeepEval 质量评估框架（默认 false，使用自建 Judge）。"""
        value = self.get("USE_DEEPEVAL")
        return value is not None and value.lower() == "true"


config = Config()  # 全局配置单例：测试代码统一经此入口读取配置


def resolve_pdf_path(env_key: str) -> Optional[str]:
    """解析 env_key（如 PDF_PATH / PDF_PATH_2）指向的 PDF 本地路径：归一化为绝对路径并校验存在。

    返回 str（绝对路径）或 None（未配置 / 文件不存在），跳过与告警文案由调用方（fixture）决定。
    原先 paper_interpret 与 robust 各有一份相同逻辑的 fixture 实现，收敛于此单一入口。
    """
    raw = config.get(env_key)
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if not p.is_file():
        return None
    return str(p)

# 启动时打印当前环境（便于确认）
print(f"[环境配置] 当前环境：{config.current_env}（{config.env_description}）")
if config.get("BASE_URL"):
    print(f"[环境配置] BASE_URL 已手动覆盖：{config.base_url}")
else:
    print(f"[环境配置] 使用 environments.yaml 配置：{config.base_url}")
