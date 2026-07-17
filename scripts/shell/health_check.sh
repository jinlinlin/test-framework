#!/usr/bin/env bash
# =============================================================================
# 健康检查脚本 — 检查被测系统连通性、框架核心服务状态
#
# 用法：./health_check.sh [--config FILE]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; RESET='\033[0m'
log_pass() { echo -e "${GREEN}[PASS]${RESET} $*"; }
log_fail() { echo -e "${RED}[FAIL]${RESET} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${RESET} $*"; }

FAILURES=0

# --------------------------------------------------------------------------
# 检查项
# --------------------------------------------------------------------------

# 检查 Python 环境
check_python_env() {
    if python3 -c "import test_framework" 2>/dev/null; then
        log_pass "test_framework 模块可导入"
    else
        log_fail "test_framework 模块不可导入"
        FAILURES=$((FAILURES + 1))
    fi
}

# 检查 Node.js 环境
check_node_env() {
    if [ -d "$FRAMEWORK_ROOT/nodejs_modules/node_modules" ]; then
        log_pass "Node.js 依赖已安装"
    else
        log_warn "Node.js 依赖未安装"
    fi
}

# 检查配置文件
check_configs() {
    local config_dir="$FRAMEWORK_ROOT/config"
    if [ -d "$config_dir" ]; then
        log_pass "配置目录存在"
    else
        log_fail "配置目录不存在"
        FAILURES=$((FAILURES + 1))
    fi
}

# 检查输出目录
check_output_dirs() {
    for dir in logs reports results artifacts; do
        if [ -d "$FRAMEWORK_ROOT/$dir" ]; then
            log_pass "输出目录存在: $dir"
        else
            log_warn "输出目录不存在: $dir（将自动创建）"
            mkdir -p "$FRAMEWORK_ROOT/$dir"
        fi
    done
}

# 检查端口连通性（如指定目标系统）
check_target_ports() {
    local targets="${1:-}"
    if [ -z "$targets" ]; then
        return
    fi
    IFS=',' read -ra ADDR <<< "$targets"
    for addr in "${ADDR[@]}"; do
        host=$(echo "$addr" | cut -d: -f1)
        port=$(echo "$addr" | cut -d: -f2)
        if timeout 3 bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
            log_pass "连通: $host:$port"
        else
            log_fail "不可达: $host:$port"
            FAILURES=$((FAILURES + 1))
        fi
    done
}

# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
echo "=== 健康检查 ==="
check_python_env
check_node_env
check_configs
check_output_dirs
check_target_ports "${TARGETS:-}"

echo ""
if [ $FAILURES -eq 0 ]; then
    log_pass "所有检查通过"
    exit 0
else
    log_fail "$FAILURES 项检查失败"
    exit 1
fi
