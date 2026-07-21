#!/usr/bin/env bash
# =============================================================================
# 环境安装脚本 — 检测并安装 Python、Node.js、Playwright 等依赖
#
# 用法：
#   ./setup.sh           # 完整安装
#   ./setup.sh --check-only  # 仅检测，不安装
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RESET='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${RESET}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

CHECK_ONLY=false
[[ "${1:-}" == "--check-only" ]] && CHECK_ONLY=true

ERRORS=0

# --------------------------------------------------------------------------
# 检测函数
# --------------------------------------------------------------------------
check_python() {
    if command -v python3 &>/dev/null; then
        PY_VER=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
        log_info "Python $PY_VER 已安装"
    elif command -v python &>/dev/null; then
        PY_VER=$(python --version 2>&1 | grep -oP '\d+\.\d+')
        log_info "Python $PY_VER 已安装"
    else
        log_error "Python 未安装"
        ERRORS=$((ERRORS + 1))
        [ "$CHECK_ONLY" = false ] && log_warn "请安装 Python 3.10+"
    fi
}

check_node() {
    if command -v node &>/dev/null; then
        NODE_VER=$(node --version)
        log_info "Node.js $NODE_VER 已安装"
    else
        log_error "Node.js 未安装"
        ERRORS=$((ERRORS + 1))
        [ "$CHECK_ONLY" = false ] && log_warn "请安装 Node.js 18+"
    fi
}

check_pnpm() {
    if command -v pnpm &>/dev/null; then
        PNPM_VER=$(pnpm --version)
        log_info "pnpm $PNPM_VER 已安装"
    else
        log_error "pnpm 未安装"
        ERRORS=$((ERRORS + 1))
        [ "$CHECK_ONLY" = false ] && log_warn "请安装 pnpm: npm install -g pnpm"
    fi
}

check_playwright() {
    if python3 -c "import playwright" 2>/dev/null; then
        log_info "Playwright (Python) 已安装"
    else
        log_warn "Playwright (Python) 未安装"
        if [ "$CHECK_ONLY" = false ]; then
            log_info "正在安装 Playwright..."
            pip install playwright 2>/dev/null || log_error "Playwright 安装失败"
            playwright install chromium 2>/dev/null || log_error "Playwright 浏览器安装失败"
        else
            ERRORS=$((ERRORS + 1))
        fi
    fi
}

install_python_deps() {
    log_info "安装 Python 依赖..."
    local req_file="$FRAMEWORK_ROOT/python_modules/requirements.txt"
    local pyproject_file="$FRAMEWORK_ROOT/python_modules/pyproject.toml"
    
    if command -v uv &>/dev/null; then
        log_info "使用 uv 安装 Python 依赖..."
        if [ -f "$pyproject_file" ]; then
            cd "$FRAMEWORK_ROOT/python_modules" && uv pip install -r "$req_file"
        elif [ -f "$req_file" ]; then
            uv pip install -r "$req_file"
        else
            log_warn "requirements.txt 不存在: $req_file"
        fi
    elif command -v pip &>/dev/null; then
        log_info "使用 pip 安装 Python 依赖..."
        if [ -f "$req_file" ]; then
            pip install -r "$req_file"
        else
            log_warn "requirements.txt 不存在: $req_file"
        fi
    else
        log_error "uv 和 pip 都未安装，无法安装 Python 依赖"
        ERRORS=$((ERRORS + 1))
        return
    fi
    log_info "Python 依赖安装完成"
}

install_node_deps() {
    log_info "安装 Node.js 依赖..."
    local node_dir="$FRAMEWORK_ROOT/nodejs_modules"
    if [ -d "$node_dir" ] && [ -f "$node_dir/package.json" ]; then
        if command -v pnpm &>/dev/null; then
            cd "$node_dir" && pnpm install
            log_info "Node.js 依赖安装完成"
        else
            log_error "pnpm 未安装，请先安装: npm install -g pnpm"
            ERRORS=$((ERRORS + 1))
        fi
    else
        log_warn "nodejs_modules/package.json 不存在"
    fi
}

# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
log_info "=== 环境检测 ==="
check_python
check_node
check_pnpm
check_playwright

if [ "$CHECK_ONLY" = true ]; then
    if [ $ERRORS -eq 0 ]; then
        log_info "所有依赖检测通过"
        exit 0
    else
        log_error "$ERRORS 项依赖缺失"
        exit 1
    fi
fi

if [ $ERRORS -gt 0 ]; then
    log_warn "$ERRORS 项核心依赖缺失，部分安装可能失败"
fi

log_info "=== 安装依赖 ==="
install_python_deps
install_node_deps

log_info "=== 环境安装完成 ==="
