"""配置文档契约离线回归：把"文档说的"和"代码读的"逐键核对，做成常驻断言。

动机（与 uniresearch-project 自己犯过的错同类——EnvProperties.kt 注释与行为相反）：
    本项目的 config/.env.example 是新人唯一的配置入口，也是 AI 生成用例时的取值来源。
    一旦键名与代码不一致，表现为"照文档配了却不生效"或"代码读了一个文档里根本没有的键"，
    排查成本远高于现在这条 0.1 秒的断言。

本文件迁移自 uniresearch-test/agent-test 源仓，适配本仓实际：
    删 A4 的 run.py 固定点条目与 A5 的 ENV_SWITCHING.md 条目（本仓无对应物），其余全部保留。

四类被锁住的漂移：
    A1 代码读取的键必须在 .env.example 有文档（漏一个，新人就配不出来）
    A2 .env.example 里的键必须真被代码读取（僵尸键会误导，且没人敢删）
    A3 .env.example 不得写真实密钥（它是要提交 Git 的模板，文件头自己也这么要求；
       运行时只读 config/.env，改模板不影响本地）
    A4 文档承诺的命令行开关必须真实存在且插件已安装（防"照文档执行直接报错"）
    A5 environments.yaml 自洽：每个环境都有 base_url/description，default_env 写法可解析

维护约定：新增配置键时先跑这里（会红），再到 config/.env.example 补文档；
白名单条目必须写理由，且白名单里的键若已不再被代码读取，allowlist 自检会红。

运行：
    python -m pytest test_cases/paper_interpret/test_env_doc_contract_offline.py -q
"""
import importlib.util
import re
from typing import Set

import pytest
import yaml

from core.utils.config import PROJECT_ROOT, ENVIRONMENTS_FILE

pytestmark = [pytest.mark.offline]

# 示例模板路径（config.py 只导出真实 .env 路径，模板在测试侧自行定位）
ENV_EXAMPLE_PATH = PROJECT_ROOT / "config" / ".env.example"

# 被扫描的文档源（承诺配置入口或命令行开关的地方）
DOC_SOURCES = [
    "README.md",
    "pytest.ini",
    "conftest.py",
    "core/utils/config.py",
    "config/.env.example",
    "config/environments.yaml",
    "config/ENV_SWITCHING.md",
    "test_cases/paper_interpret/README.md",
]

# 扫描源码时跳过的目录（生成物/依赖/产物，不属于被测代码）
SKIP_DIRS = {
    ".venv", "__pycache__", "reports", "test_output", "logs", ".deepeval",
    ".pytest_cache", ".git", "node_modules", "allure-results", "allure-report", ".qoder",
}

KEY_NAME = r"[A-Z][A-Z0-9_]{2,}"

# 读取型：要求文档化
READ_PATTERNS = [
    # Config.get / Config.require（属性实现里写作 self.get）
    re.compile(rf"\b(?:config|self|cfg|c)\.(?:get|require)\(\s*[\"']({KEY_NAME})[\"']"),
    re.compile(rf"\bos\.getenv\(\s*[\"']({KEY_NAME})[\"']"),
    re.compile(rf"\bos\.environ\.get\(\s*[\"']({KEY_NAME})[\"']"),
    # 间接读取封装：resolve_pdf_path 等以键名作参数的通用解析入口（键经 config.get 动态读取）
    re.compile(rf"\bresolve_pdf_path\(\s*[\"']({KEY_NAME})[\"']"),
]

# 探针型键：用例自己 monkeypatch.setenv/delenv 出来的假键（如配置读取行为测试的输入），
# 它们不是真实配置项，必须从核对范围排除——否则测试自身会误报成"未文档化"。
PROBE_PATTERN = re.compile(rf"monkeypatch\.(?:setenv|delenv)\(\s*[\"']({KEY_NAME})[\"']")

# A1 白名单：被读取但不该出现在 .env.example 的键，逐条给理由
#（注：写入型键如 DEEPEVAL_*、PYTHONIOENCODING、续期回写的 TOKEN 不属于本核对范围，
#  它们不以 get/require 形式出现，READ_PATTERNS 天然不会匹配）
# 源仓同款：本仓 conftest.py 的 artifact 目录也读此键（os.environ.get），但它非用户配置项，
# 由多模型对比脚本运行时注入，故走白名单而非模板
READ_ALLOWLIST = {
    "TEST_MODEL_OUTPUT_DIR": "多模型对比时由调用方运行时注入（conftest.py 覆盖产物目录），非用户配置项",
}

# A4 白名单：pytest 内建选项（无需插件）
PYTEST_BUILTIN_OPTIONS = {
    "tb", "collect-only", "capture", "markers", "rootdir", "override-ini",
    "color", "maxfail", "stop", "ignore", "disable-warnings", "continue-on-collection-errors",
}

# A4 白名单：插件选项 → 提供该选项的包名（必须实测已安装，防止文档承诺了没装的插件）
PLUGIN_OPTIONS = {
    "force-reruns": "pytest_rerunfailures",
    "reruns": "pytest_rerunfailures",
    "reruns-delay": "pytest_rerunfailures",
    "html": "pytest_html",
    "self-contained-html": "pytest_html",
    "alluredir": "allure_pytest",
    "allure-no-capture": "allure_pytest",
}

# A3 疑似真实密钥的形态（模板文件只允许占位符）
SECRET_PATTERNS = [
    (re.compile(r"pk-lf-[0-9a-f]{8,}", re.I), "疑似真实 Langfuse Public Key"),
    (re.compile(r"sk-lf-[0-9a-f]{8,}", re.I), "疑似真实 Langfuse Secret Key"),
    (re.compile(r"Basic\s+[A-Za-z0-9+/]{16,}={0,2}"), "疑似真实 Basic 凭据"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\."), "疑似真实 JWT/Token"),
]


def _source_files() -> list:
    return [
        p for p in PROJECT_ROOT.rglob("*.py")
        if not any(part in SKIP_DIRS for part in p.parts)
    ]


def _read_keys() -> Set[str]:
    """应被文档化的配置键。

    区分读取位置很关键：TOKEN / GOLDEN_STRICT / AUTHORIZATION 既被生产代码读（必须文档化），
    又被用例当 monkeypatch 探针（不能因此从必读集里抵掉）；而 AGENT_TEST_KEY_MISSING 这类
    只在 test_cases/ 里出现且被 setenv 的键才是纯探针。
    规则：非用例目录的读取一律有义务文档化；用例目录的读取仅当它不是探针时才计。
    """
    probes: Set[str] = set()
    prod_reads: Set[str] = set()
    test_reads: Set[str] = set()
    for path in _source_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        probes.update(PROBE_PATTERN.findall(text))
        found: Set[str] = set()
        for pattern in READ_PATTERNS:
            found.update(pattern.findall(text))
        if "test_cases" in path.parts:
            test_reads.update(found)
        else:
            prod_reads.update(found)
    return prod_reads | (test_reads - probes)


def _example_keys() -> Set[str]:
    """.env.example 的键：`KEY=` 与注释掉的 `# KEY=`（可选提示）都算已文档化。"""
    keys: Set[str] = set()
    for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        match = re.match(rf"^\s*#?\s*({KEY_NAME})\s*=", line)
        if match:
            keys.add(match.group(1))
    return keys


def _example_active_values() -> list:
    """仅未注释的生效行 [(key, value)]——注释行是占位说明，不含真实值。"""
    pairs = []
    for line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(rf"^({KEY_NAME})\s*=\s*(.*)$", stripped)
        if match:
            pairs.append((match.group(1), match.group(2)))
    return pairs


def _defined_cli_options() -> Set[str]:
    """代码里真实定义的命令行开关：conftest 的 addoption + scripts/ 下的 argparse。"""
    options: Set[str] = set()
    for path in [PROJECT_ROOT / "conftest.py", *sorted((PROJECT_ROOT / "scripts").glob("*.py"))]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        options.update(re.findall(r'add_argument\(\s*["\']--([a-z][a-z0-9-]*)', text))
        options.update(re.findall(r'addoption\(\s*["\']--([a-z][a-z0-9-]*)', text))
    return options


def _doc_cli_options() -> Set[str]:
    options: Set[str] = set()
    for rel in DOC_SOURCES:
        path = PROJECT_ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        options.update(re.findall(r"--([a-z][a-z0-9-]*)", text))
    return options


class TestEnvKeyDocumentation:
    """A1/A2：键名双向核对，杜绝"代码读了文档没有的键"与"文档留着代码不读的键"。"""

    def test_代码读取的键必须有文档(self):
        undocumented = _read_keys() - _example_keys() - set(READ_ALLOWLIST)
        assert not undocumented, (
            f"以下环境变量被代码读取但 config/.env.example 未文档化：{sorted(undocumented)}。"
            "新人照模板配置后功能静默不生效，请补键名与中文说明（可选项用 # KEY= 形式）"
        )

    def test_文档里的键必须被代码读取(self):
        zombies = _example_keys() - _read_keys()
        assert not zombies, (
            f"config/.env.example 中的键未被任何代码读取：{sorted(zombies)}。"
            "僵尸配置项会让接手人误以为有效（要么实现它，要么删除）"
        )

    def test_白名单条目不得变成僵尸(self):
        """白名单是"确有理由不文档化"；键消失说明理由已失效，必须清理条目。"""
        stale = {k for k in READ_ALLOWLIST if k not in _read_keys()}
        assert not stale, f"READ_ALLOWLIST 中的键已不再被代码读取，请删除条目：{sorted(stale)}"

    def test_扫描器自身不得空转(self):
        """防假绿：正则一旦失配（比如重命名 config 变量、改掉读取写法），上面三条会集体"通过"却什么也不守。

        这里的固定点是"确定被代码读取、确定应当文档化"的键，它们不在集内就说明扫描坏了。
        """
        reads = _read_keys()
        for anchor in ("TOKEN", "PDF_PATH", "DATASET_ID", "MODEL_NAME", "JUDGE_MODEL"):
            assert anchor in reads, f"键 {anchor} 确实被代码读取却没被扫到，READ_PATTERNS 已失效"
        example = _example_keys()
        for anchor in ("TOKEN", "PDF_PATH", "DATASET_ID", "MODEL_NAME", "LANGFUSE_HOST"):
            assert anchor in example, f"模板缺少常见键 {anchor}，_example_keys 解析已失效或模板被截断"
        assert len(reads) >= 10 and len(example) >= 15, (
            f"读到的键 {len(reads)} 个 / 模板键 {len(example)} 个，规模异常疑似扫描失效"
        )


class TestEnvExampleNoSecrets:
    """A3：模板随仓库分发，不允许携带真实凭据。"""

    def test_示例文件不得含疑似真实密钥(self):
        offenders = []
        for key, value in _example_active_values():
            for pattern, reason in SECRET_PATTERNS:
                if pattern.search(value):
                    offenders.append(f"{key}（{reason}）")
        assert not offenders, (
            f"config/.env.example 出现疑似真实凭据：{offenders}。"
            "该文件要提交 Git，请改为占位符（真实值放本地 config/.env，运行时只读 .env）"
        )


class TestDocPromisedCliOptions:
    """A4：文档承诺的开关必须可用且插件确已安装。"""

    def test_文档提到的命令行开关必须可用(self):
        defined = _defined_cli_options()
        unavailable = []
        for opt in sorted(_doc_cli_options()):
            if opt in defined or opt in PYTEST_BUILTIN_OPTIONS:
                continue
            plugin = PLUGIN_OPTIONS.get(opt)
            if plugin and importlib.util.find_spec(plugin):
                continue
            if plugin:
                unavailable.append(f"--{opt}（需插件 {plugin}，实测未安装）")
            else:
                unavailable.append(f"--{opt}（conftest/scripts 中无定义）")
        assert not unavailable, (
            f"文档承诺了不可用的命令行开关：{unavailable}。"
            "要么实现它，要么把文档改成真实存在的入口——照文档执行会直接报错或静默无效"
        )


class TestEnvironmentsYamlSelfConsistency:
    """A5：环境配置自洽，且模板提到的环境名真实存在。"""

    @pytest.fixture
    def env_yaml(self) -> dict:
        return yaml.safe_load(ENVIRONMENTS_FILE.read_text(encoding="utf-8"))

    def test_每个环境都有base_url与description(self, env_yaml):
        envs = env_yaml.get("environments", {})
        assert envs, "environments.yaml 未定义任何环境"
        for name, cfg in envs.items():
            assert cfg.get("base_url"), f"环境 {name} 缺 base_url，切过去会直接抛 ConfigError"
            assert cfg.get("description"), f"环境 {name} 缺 description，启动横幅会显示成裸名"
            assert not cfg["base_url"].endswith("/"), f"环境 {name} 的 base_url 不应带尾部斜杠"

    def test_default_env写法与解析函数兼容(self, env_yaml):
        """_resolve_env_name 只认字面环境名或 ${TEST_ENV:-xxx} 占位形式，其余写法会被当环境名查不到。"""
        default = env_yaml.get("default_env", "")
        valid = default.startswith("${") or default in env_yaml.get("environments", {})
        assert valid, f"default_env={default!r} 既非 ${{...}} 占位也非已定义环境名"

    def test_模板示例环境名必须在yaml存在(self, env_yaml):
        """源仓此条核对 ENV_SWITCHING.md（本仓无），改核 .env.example 的 TEST_ENV 示例值：
        模板注释里推荐的环境名如果在 yaml 中不存在，新人照抄切不过去。"""
        envs = set(env_yaml.get("environments", {}))
        text = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
        mentioned = set(re.findall(r"\b(dev|test|pre|prod)\b", text))
        assert mentioned, "模板未提及任何环境名——检查 TEST_ENV 说明是否被误删（本条会变成假绿）"
        missing = mentioned - envs
        assert not missing, f"模板提到的环境在 yaml 中不存在：{sorted(missing)}"
