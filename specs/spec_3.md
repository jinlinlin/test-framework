# Spec 3：多语言桥接层

## 1. 概述

本 Spec 实现框架的多语言协同架构，通过桥接模式将 Python、Node.js、Shell 三种语言解耦，支持独立运行与互相调用。  
Python 核心框架可通过子进程或 IPC 通信调度 Node.js 高性能引擎，Shell 负责运维调度，三者日志/上下文/配置体系完全统一。

**依赖**：Spec 1（core/interfaces/executable.py, core/events/event_bus.py）, Spec 2（config/manager.py）  
**被依赖**：Spec 4 ~ Spec 6（测试引擎层）、Spec 10（脚本层）

---

## 2. 目标目录结构

```
uniplore-test-framework/
└── languages/
    ├── __init__.py
    ├── bridge.py              # 桥接器基类（抽象）
    ├── bridge_factory.py      # 桥接工厂（工厂模式）
    │
    ├── python/
    │   ├── __init__.py
    │   ├── executor.py        # Python 执行器
    │   ├── subprocess_runner.py
    │   └── native_bridge.py   # 原生桥接（直接调用）
    │
    ├── nodejs/
    │   ├── __init__.py
    │   ├── executor.py        # Node 执行器
    │   ├── node_runner.py     # 运行 Node 脚本
    │   ├── ipc_bridge.py      # IPC 通信桥接
    │   ├── bridge.js          # Node 端桥接脚本
    │   └── package.json
    │
    └── shell/
        ├── __init__.py
        ├── executor.py        # Shell 执行器
        ├── shell_runner.py    # 运行 Shell 脚本
        └── scripts/
            └── common.sh      # 公共 Shell 函数
```

---

## 3. 详细设计

### 3.1 bridge.py — 桥接器基类

```python
"""
设计模式：桥接模式 — 抽象部分与实现部分分离
职责：定义多语言桥接的统一接口，所有语言桥接器必须继承此类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime

@dataclass
class ExecutionResult:
    language: str
    script: str
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    data: Dict[str, Any] = field(default_factory=dict)
    success: bool = True

class LanguageBridge(ABC):
    """语言桥接器基类"""

    @property
    @abstractmethod
    def language(self) -> str: ...

    @abstractmethod
    async def execute(self, script_or_callable: Any,
                      args: Dict[str, Any] = None,
                      timeout: float = 300) -> ExecutionResult: ...

    @abstractmethod
    async def is_available(self) -> bool:
        """检测该语言运行环境是否可用"""

    @abstractmethod
    def get_version(self) -> Optional[str]: ...

    async def execute_with_context(self, script_or_callable: Any,
                                   context: 'ExecutionContext',
                                   **kwargs) -> ExecutionResult:
        """携带执行上下文的调用，自动注入配置和目标信息"""
```

### 3.2 bridge_factory.py — 桥接工厂（工厂模式）

```python
"""
设计模式：工厂模式
职责：根据语言名称返回对应桥接器实例，支持动态注册新语言
"""
class BridgeFactory:
    _registry: Dict[str, Type[LanguageBridge]] = {}

    @classmethod
    def register(cls, language: str, bridge_cls: Type[LanguageBridge]) -> None: ...

    @classmethod
    def create(cls, language: str, **kwargs) -> LanguageBridge: ...

    @classmethod
    def available_languages(cls) -> List[str]: ...

    @classmethod
    async def create_all_available(cls) -> Dict[str, LanguageBridge]: ...
```

### 3.3 Python 桥接

#### python/executor.py

```python
"""
职责：Python 语言的执行器，支持两种模式：
  - native：直接调用 Python 函数/类（同进程）
  - subprocess：通过子进程运行独立 Python 脚本
"""
class PythonExecutor(LanguageBridge):
    def __init__(self, mode: str = "native"):
        self._mode = mode

    @property
    def language(self) -> str:
        return "python"

    async def execute(self, script_or_callable, args=None, timeout=300) -> ExecutionResult:
        if self._mode == "native":
            return await self._execute_native(script_or_callable, args, timeout)
        else:
            return await self._execute_subprocess(script_or_callable, args, timeout)

    async def _execute_native(self, callable_, args, timeout) -> ExecutionResult:
        """同进程直接调用，捕获异常并封装为 ExecutionResult"""

    async def _execute_subprocess(self, script_path, args, timeout) -> ExecutionResult:
        """使用 asyncio.create_subprocess_exec 运行独立脚本"""

    async def is_available(self) -> bool:
        return True  # Python 自身始终可用

    def get_version(self) -> str:
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
```

#### python/subprocess_runner.py

```python
"""
职责：封装子进程运行细节，处理超时、输出捕获、退出码解析
"""
class SubprocessRunner:
    async def run(self, cmd: List[str], cwd: str = None,
                  env: Dict = None, timeout: float = 300,
                  capture: bool = True) -> ExecutionResult: ...

    async def run_python(self, script: str, args: List[str] = None,
                         timeout: float = 300) -> ExecutionResult: ...

    async def run_with_streaming(self, cmd: List[str],
                                 on_stdout: Callable = None,
                                 on_stderr: Callable = None) -> ExecutionResult: ...
```

#### python/native_bridge.py

```python
"""
职责：原生桥接，在 Python 进程内直接调用模块/类/函数
支持动态导入和反射调用
"""
class NativeBridge:
    def call(self, module_path: str, callable_name: str,
             *args, **kwargs) -> Any: ...

    def load_module(self, module_path: str) -> Any: ...

    def invoke(self, obj: Any, method: str, *args, **kwargs) -> Any: ...
```

### 3.4 Node.js 桥接

#### nodejs/executor.py

```python
"""
职责：Node.js 语言执行器，通过子进程运行 Node 脚本
支持 JSON 序列化结果回传
"""
class NodeExecutor(LanguageBridge):
    def __init__(self, node_path: str = "node", modules_dir: str = "nodejs_modules"):
        self._node_path = node_path
        self._modules_dir = modules_dir

    @property
    def language(self) -> str:
        return "nodejs"

    async def execute(self, script_or_callable, args=None, timeout=300) -> ExecutionResult:
        """通过 subprocess 运行 node bridge.js --script=xxx --args=json"""

    async def is_available(self) -> bool:
        """检测 node 是否可执行"""

    def get_version(self) -> Optional[str]:
        """node --version"""
```

#### nodejs/node_runner.py

```python
"""
职责：Node 脚本运行器，封装 node 进程启动和参数传递
"""
class NodeRunner:
    def __init__(self, node_path: str, modules_dir: str): ...

    async def run_script(self, script_path: str, args: Dict = None,
                         timeout: float = 300) -> ExecutionResult: ...

    async def run_inline(self, js_code: str, timeout: float = 60) -> ExecutionResult: ...

    def _build_command(self, script: str, args: Dict) -> List[str]: ...
```

#### nodejs/ipc_bridge.py

```python
"""
职责：Python ↔ Node.js 的 IPC 双向通信桥接
使用 Unix Domain Socket / Named Pipe 实现低延迟数据交换
"""
class IPCBridge:
    def __init__(self, socket_path: str = None): ...

    async def start(self) -> None:
        """启动 IPC 服务端（Node 侧监听）"""

    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """发送消息并等待响应"""

    async def stop(self) -> None: ...

    async def is_connected(self) -> bool: ...
```

#### nodejs/bridge.js

```javascript
/**
 * Node 端桥接脚本
 * 职责：
 *   1. 接收 Python 传入的 JSON 参数（stdin / 命令行参数）
 *   2. 执行指定的 JS 模块/函数
 *   3. 将结果以 JSON 格式输出到 stdout
 *
 * 用法：node bridge.js --module=./api_load_test.js --args='{"url":"..."}'
 */

const { execSync } = require('child_process');
const path = require('path');

async function main() {
    const args = parseArgs(process.argv.slice(2));
    try {
        const modulePath = path.resolve(args.module);
        const mod = require(modulePath);
        const result = await (mod.default || mod)(JSON.parse(args.args || '{}'));
        console.log(JSON.stringify({ success: true, data: result }));
    } catch (error) {
        console.log(JSON.stringify({
            success: false,
            error: error.message,
            stack: error.stack
        }));
        process.exit(1);
    }
}

function parseArgs(argv) {
    const result = {};
    argv.forEach(arg => {
        const [key, value] = arg.replace(/^--/, '').split('=');
        result[key] = value;
    });
    return result;
}

main();
```

#### nodejs/package.json

```json
{
  "name": "uniplore-test-framework-nodejs",
  "version": "1.0.0",
  "description": "Node.js bridge for uniplore test framework",
  "main": "bridge.js",
  "scripts": {
    "test": "node --test"
  },
  "dependencies": {
    "playwright": "^1.40.0",
    "@grpc/grpc-js": "^1.9.0",
    "ws": "^8.14.0",
    "axios": "^1.6.0"
  }
}
```

### 3.5 Shell 桥接

#### shell/executor.py

```python
"""
职责：Shell 语言执行器，运行 Bash/Zsh/PowerShell 脚本
自动适配 Windows（PowerShell）和 Linux（Bash）
"""
class ShellExecutor(LanguageBridge):
    def __init__(self, shell: str = None):
        self._shell = shell or self._detect_shell()

    @property
    def language(self) -> str:
        return "shell"

    async def execute(self, script_or_callable, args=None, timeout=300) -> ExecutionResult:
        """运行 shell 脚本或命令"""

    async def is_available(self) -> bool:
        return True

    def get_version(self) -> Optional[str]: ...

    def _detect_shell(self) -> str:
        """检测当前 OS 默认 shell"""
```

#### shell/shell_runner.py

```python
"""
职责：Shell 脚本运行器，处理脚本执行、环境变量注入、输出解析
"""
class ShellRunner:
    async def run_script(self, script_path: str, env: Dict = None,
                         timeout: float = 300) -> ExecutionResult: ...

    async def run_command(self, command: str, cwd: str = None,
                          timeout: float = 60) -> ExecutionResult: ...

    async def run_with_sudo(self, command: str, password: str = None,
                            timeout: float = 60) -> ExecutionResult: ...
```

#### shell/scripts/common.sh

```bash
#!/usr/bin/env bash
# 公共 Shell 函数库

log_info()  { echo "[INFO]  $(date '+%Y-%m-%d %H:%M:%S') $*"; }
log_warn()  { echo "[WARN]  $(date '+%Y-%m-%d %H:%M:%S') $*" >&2; }
log_error() { echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $*" >&2; }

check_command() {
    command -v "$1" >/dev/null 2>&1 || { log_error "$1 not found"; return 1; }
}

wait_for_port() {
    local host=$1 port=$2 timeout=${3:-30}
    local elapsed=0
    while ! nc -z "$host" "$port" 2>/dev/null; do
        sleep 1
        elapsed=$((elapsed + 1))
        [ $elapsed -ge $timeout ] && { log_error "Timeout waiting for $host:$port"; return 1; }
    done
    log_info "Port $host:$port is ready"
}

kill_process_on_port() {
    local port=$1
    local pid=$(lsof -ti :$port 2>/dev/null)
    [ -n "$pid" ] && kill -9 $pid && log_info "Killed process $pid on port $port"
}

json_result() {
    # 输出标准化 JSON 结果供 Python 解析
    local success=$1 data=$2
    echo "{\"success\": $success, \"data\": $data}"
}
```

---

## 4. 多语言协同流程

```
Shell (run.sh)
    │
    ├─ 环境初始化 / 依赖检测
    │
    ├─ 调用 Python 主框架
    │      │
    │      ├─ 直接执行 Python 引擎（web/db/api/penetration/auth/qa）
    │      │
    │      └─ 调度 Node.js 高性能引擎（通过 IPC/subprocess）
    │             │
    │             └─ 执行完毕输出 JSON 结果
    │                    │
    │                    └─ Python 聚合结果 → 生成报告
    │
    └─ 退出，返回汇总状态码
```

---

## 5. 验收标准

- [ ] `LanguageBridge` 抽象基类接口清晰，无法直接实例化
- [ ] `BridgeFactory` 可按语言名创建桥接器，支持动态注册
- [ ] `PythonExecutor` native 模式可调用 Python 函数并捕获结果
- [ ] `PythonExecutor` subprocess 模式可运行独立 Python 脚本
- [ ] `NodeExecutor` 可通过 `bridge.js` 运行 Node 脚本并解析 JSON 结果
- [ ] `IPCBridge` 可实现 Python ↔ Node.js 双向通信
- [ ] `ShellExecutor` 可正确运行 Shell 脚本，自动适配 Windows/Linux
- [ ] `common.sh` 公共函数可被其他脚本正确 source
- [ ] 三种语言均可独立执行测试任务并输出标准化 `ExecutionResult`
- [ ] 全模块有完整单元测试覆盖
