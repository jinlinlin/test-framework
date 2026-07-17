#!/usr/bin/env bash
# =============================================================================
# 框架主入口脚本
#
# 用法：./run.sh [options]
#   -e, --env       环境（dev/test/staging/production）
#   -t, --type      测试类型（web_performance/backend/rest_api/database/...）
#   -c, --config    配置文件路径
#   -p, --plan      测试计划文件
#   --parallel      并行执行
#   --dry-run       仅验证配置，不执行
#   -h, --help      显示帮助信息
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# --------------------------------------------------------------------------
# 颜色定义
# --------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RESET='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${RESET}  $(date '+%Y-%m-%d %H:%M:%S') | $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $(date '+%Y-%m-%d %H:%M:%S') | $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $(date '+%Y-%m-%d %H:%M:%S') | $*" >&2; }

# --------------------------------------------------------------------------
# 参数解析
# --------------------------------------------------------------------------
ENV="dev"
TEST_TYPE=""
CONFIG=""
PLAN=""
PARALLEL=false
DRY_RUN=false

show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -e, --env ENV       运行环境 (dev/test/staging/production)"
    echo "  -t, --type TYPE     测试类型 (web_performance/backend/rest_api/database/...)"
    echo "  -c, --config FILE   配置文件路径"
    echo "  -p, --plan FILE     测试计划文件"
    echo "  --parallel          启用并行执行"
    echo "  --dry-run           仅验证配置，不实际执行"
    echo "  -h, --help          显示此帮助信息"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)      ENV="$2"; shift 2 ;;
        -t|--type)     TEST_TYPE="$2"; shift 2 ;;
        -c|--config)   CONFIG="$2"; shift 2 ;;
        -p|--plan)     PLAN="$2"; shift 2 ;;
        --parallel)    PARALLEL=true; shift ;;
        --dry-run)     DRY_RUN=true; shift ;;
        -h|--help)     show_help; exit 0 ;;
        *)             log_error "未知选项: $1"; show_help; exit 1 ;;
    esac
done

# --------------------------------------------------------------------------
# 执行流程
# --------------------------------------------------------------------------
log_info "=========================================="
log_info "Uniplore Test Framework"
log_info "=========================================="
log_info "环境:       $ENV"
log_info "测试类型:   ${TEST_TYPE:-全部}"
log_info "配置文件:   ${CONFIG:-默认}"
log_info "测试计划:   ${PLAN:-无}"
log_info "并行执行:   $PARALLEL"
log_info "试运行:     $DRY_RUN"
log_info "框架根目录: $FRAMEWORK_ROOT"
log_info "=========================================="

# 环境检查
if bash "$SCRIPT_DIR/setup.sh" --check-only 2>/dev/null; then
    log_info "环境检查通过"
else
    log_warn "环境检查失败，某些依赖可能未安装"
fi

# 试运行模式
if [ "$DRY_RUN" = true ]; then
    log_info "试运行模式 — 仅验证配置"
    python -m test_framework --env "$ENV" --dry-run \
        ${TEST_TYPE:+--type "$TEST_TYPE"} \
        ${CONFIG:+--config "$CONFIG"} \
        ${PLAN:+--plan "$PLAN"}
    exit $?
fi

# 构建执行参数
ARGS="--env $ENV"
[ -n "$TEST_TYPE" ] && ARGS="$ARGS --type $TEST_TYPE"
[ -n "$CONFIG" ]    && ARGS="$ARGS --config $CONFIG"
[ -n "$PLAN" ]      && ARGS="$ARGS --plan $PLAN"
[ "$PARALLEL" = true ] && ARGS="$ARGS --parallel"

# 执行 Python 主框架
log_info "启动框架: python -m test_framework $ARGS"
cd "$FRAMEWORK_ROOT"
python -m test_framework $ARGS

EXIT_CODE=$?
log_info "框架退出码: $EXIT_CODE"
exit $EXIT_CODE
