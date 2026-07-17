#!/usr/bin/env bash
# =============================================================================
# Shell 工具函数库 — 提供常用的 Shell 辅助函数。
#
# 使用方法：
#   source shell_utils.sh
#   log_info "服务启动成功"
#   check_command "docker"
# =============================================================================

set -euo pipefail

# --------------------------------------------------------------------------
# 颜色定义
# --------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RESET='\033[0m'

# --------------------------------------------------------------------------
# 日志函数
# --------------------------------------------------------------------------

# 输出信息日志（绿色）
log_info() {
    echo -e "${GREEN}[INFO]${RESET} $(date '+%Y-%m-%d %H:%M:%S') | $*"
}

# 输出警告日志（黄色）
log_warn() {
    echo -e "${YELLOW}[WARN]${RESET} $(date '+%Y-%m-%d %H:%M:%S') | $*"
}

# 输出错误日志（红色）
log_error() {
    echo -e "${RED}[ERROR]${RESET} $(date '+%Y-%m-%d %H:%M:%S') | $*" >&2
}

# 输出调试日志（青色，仅在 DEBUG=1 时显示）
log_debug() {
    if [[ "${DEBUG:-0}" == "1" ]]; then
        echo -e "${CYAN}[DEBUG]${RESET} $(date '+%Y-%m-%d %H:%M:%S') | $*"
    fi
}

# --------------------------------------------------------------------------
# 检测函数
# --------------------------------------------------------------------------

# 检查命令是否存在
check_command() {
    local cmd="$1"
    if ! command -v "$cmd" &>/dev/null; then
        log_error "命令不存在: $cmd"
        return 1
    fi
    log_debug "命令已找到: $cmd"
    return 0
}

# 检查端口是否可用
check_port() {
    local host="${1:-localhost}"
    local port="$2"
    local timeout="${3:-3}"

    if timeout "$timeout" bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
        log_debug "端口可用: $host:$port"
        return 0
    else
        log_debug "端口不可用: $host:$port"
        return 1
    fi
}

# 等待端口可用
wait_for_port() {
    local host="${1:-localhost}"
    local port="$2"
    local timeout="${3:-30}"
    local interval="${4:-2}"
    local elapsed=0

    log_info "等待 $host:$port 可用 (超时 ${timeout}s)..."
    while [ "$elapsed" -lt "$timeout" ]; do
        if check_port "$host" "$port" 2; then
            log_info "$host:$port 已可用 (${elapsed}s)"
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done

    log_error "等待超时: $host:$port (${timeout}s)"
    return 1
}

# --------------------------------------------------------------------------
# 文件/目录辅助
# --------------------------------------------------------------------------

# 确保目录存在
ensure_dir() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        log_debug "已创建目录: $dir"
    fi
}

# 清理目录内容（保留目录本身）
clean_dir() {
    local dir="$1"
    if [ -d "$dir" ]; then
        rm -rf "${dir:?}"/*
        log_debug "已清理目录: $dir"
    fi
}

# 获取脚本所在目录
get_script_dir() {
    local source="${BASH_SOURCE[0]}"
    while [ -L "$source" ]; do
        local dir
        dir=$(cd -P "$(dirname "$source")" && pwd)
        source=$(readlink "$source")
        [[ "$source" != /* ]] && source="$dir/$source"
    done
    cd -P "$(dirname "$source")" && pwd
}

# --------------------------------------------------------------------------
# HTTP 辅助
# --------------------------------------------------------------------------

# 发送 HTTP GET 请求（使用 curl 或 wget）
http_get() {
    local url="$1"
    local output="${2:-}"

    if command -v curl &>/dev/null; then
        if [ -n "$output" ]; then
            curl -sSfL "$url" -o "$output"
        else
            curl -sSfL "$url"
        fi
    elif command -v wget &>/dev/null; then
        if [ -n "$output" ]; then
            wget -q "$url" -O "$output"
        else
            wget -qO- "$url"
        fi
    else
        log_error "curl 和 wget 均不可用"
        return 1
    fi
}

# 检查 HTTP 服务是否返回 200
http_health_check() {
    local url="$1"
    local timeout="${2:-5}"
    local status

    if command -v curl &>/dev/null; then
        status=$(curl -sSf -o /dev/null -w '%{http_code}' --max-time "$timeout" "$url" 2>/dev/null || echo "000")
    else
        log_error "curl 不可用，无法进行健康检查"
        return 1
    fi

    if [ "$status" = "200" ]; then
        log_debug "健康检查通过: $url (HTTP $status)"
        return 0
    else
        log_warn "健康检查失败: $url (HTTP $status)"
        return 1
    fi
}

# --------------------------------------------------------------------------
# 进程辅助
# --------------------------------------------------------------------------

# 获取占用指定端口的进程 PID
get_pid_by_port() {
    local port="$1"
    if command -v lsof &>/dev/null; then
        lsof -ti :"$port" 2>/dev/null
    elif command -v ss &>/dev/null; then
        ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K[0-9]+'
    else
        log_error "lsof 和 ss 均不可用"
        return 1
    fi
}

# 优雅停止进程（先 SIGTERM，超时后 SIGKILL）
graceful_stop() {
    local pid="$1"
    local timeout="${2:-10}"

    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
        log_debug "进程不存在: $pid"
        return 0
    fi

    log_info "正在停止进程: $pid"
    kill -TERM "$pid" 2>/dev/null || true

    local elapsed=0
    while [ "$elapsed" -lt "$timeout" ]; do
        if ! kill -0 "$pid" 2>/dev/null; then
            log_info "进程已停止: $pid"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    log_warn "强制杀死进程: $pid"
    kill -9 "$pid" 2>/dev/null || true
}
