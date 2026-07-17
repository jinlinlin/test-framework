# Shell 脚本编码规范

## 脚本头部
每个脚本必须以标准头部开始：

```bash
#!/usr/bin/env bash
#
# 脚本名称: xxx.sh
# 职责描述: 简要说明脚本的功能和用途
# 依赖: 列出脚本依赖的系统工具（如 docker, kubectl, nc）
# 用法: ./xxx.sh [options]
#   -e, --env    环境名称
#   -h, --help   显示帮助信息
#
set -euo pipefail
```

## 安全规范
- 必须使用 `set -euo pipefail`（错误退出、未定义变量报错、管道错误传播）
- 变量使用双引号包裹：`"$variable"`
- 命令替换使用 `$()` 而非反引号
- 敏感操作前必须检查前置条件

## 函数规范
- 函数名使用 snake_case
- 使用 `local` 声明局部变量
- 函数必须有头部注释说明职责

```bash
# 检查指定端口是否可用，等待直到超时
# 参数: $1=主机, $2=端口, $3=超时秒数（默认30）
wait_for_port() {
    local host="$1"
    local port="$2"
    local timeout="${3:-30}"
    ...
}
```

## 日志输出
- 使用统一日志函数：`log_info`, `log_warn`, `log_error`
- 包含时间戳：`$(date '+%Y-%m-%d %H:%M:%S')`
- error 输出到 stderr：`>&2`

## 参数解析
- 使用 `while/case` 结构解析命名参数
- 支持 `--help` 显示用法

## 跨平台兼容
- 检测 OS 类型：`uname -s`
- Windows 下使用 PowerShell 等价脚本
- 路径分隔符使用 `/`（Git Bash 兼容）

## 退出码
- 0：成功
- 1：通用错误
- 2：参数错误
- 其他：具体业务错误码
