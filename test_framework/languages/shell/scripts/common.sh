#!/usr/bin/env bash
# ============================================================
# common.sh — 公共 Shell 函数库
# ============================================================
# 用法：在其他脚本中 source 本文件
#   source "$(dirname "$0")/../languages/shell/scripts/common.sh"
#
# 提供标准化的日志、检查、等待等公共函数。
# ============================================================

set -euo pipefail

# ----- 日志函数 -----

log_info() {
    echo "[INFO]  $(date '+%Y-%m-%d %H:%M:%S') $*"
}

log_warn() {
    echo "[WARN]  $(date '+%Y-%m-%d %H:%M:%S') $*" >&2
}

log_error() {
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $*" >&2
}

log_debug() {
    if [ "${TF_DEBUG:-0}" = "1" ]; then
        echo "[DEBUG] $(date '+%Y-%m-%d %H:%M:%S') $*"
    fi
}

# ----- 检查函数 -----

check_command() {
    # 检查命令是否存在
    # 用法：check_command docker
    command -v "$1" >/dev/null 2>&1 || {
        log_error "命令未找到: $1"
        return 1
    }
    log_debug "命令检查通过: $1"
}

check_env_var() {
    # 检查环境变量是否已设置
    # 用法：check_env_var DATABASE_URL
    if [ -z "${!1:-}" ]; then
        log_error "环境变量未设置: $1"
        return 1
    fi
    log_debug "环境变量检查通过: $1"
}

# ----- 等待函数 -----

wait_for_port() {
    # 等待指定端口可用
    # 用法：wait_for_port localhost 8080 30
    local host=$1
    local port=$2
    local timeout=${3:-30}
    local elapsed=0

    while ! nc -z "$host" "$port" 2>/dev/null; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ "$elapsed" -ge "$timeout" ]; then
            log_error "等待超时: $host:$port (${timeout}s)"
            return 1
        fi
    done
    log_info "端口就绪: $host:$port"
}

wait_for_url() {
    # 等待 HTTP URL 可访问
    # 用法：wait_for_url http://localhost:8080/health 30
    local url=$1
    local timeout=${2:-30}
    local elapsed=0

    while ! curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q "200"; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ "$elapsed" -ge "$timeout" ]; then
            log_error "URL 等待超时: $url (${timeout}s)"
            return 1
        fi
    done
    log_info "URL 就绪: $url"
}

# ----- 进程管理 -----

kill_process_on_port() {
    # 终止占用指定端口的进程
    # 用法：kill_process_on_port 8080
    local port=$1
    local pid
    pid=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pid" ]; then
        kill -9 "$pid" 2>/dev/null || true
        log_info "已终止进程 $pid (端口 $port)"
    fi
}

# ----- 输出函数 -----

json_result() {
    # 输出标准化 JSON 结果供 Python 解析
    # 用法：json_result true '{"tests": 10, "passed": 9}'
    local success=$1
    local data=${2:-'{}'}
    echo "{\"success\": $success, \"data\": $data}"
}

json_error() {
    # 输出标准化 JSON 错误
    # 用法：json_error "Connection refused"
    local error_msg=$1
    echo "{\"success\": false, \"error\": \"$error_msg\"}"
}
