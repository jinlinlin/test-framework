#!/usr/bin/env bash
# =============================================================================
# 清理脚本 — 清理 logs/reports/results/artifacts 下的过期文件
#
# 用法：./cleanup.sh [--days N] [--dry-run]
#   --days N    清理 N 天前的文件（默认 30 天）
#   --dry-run   仅显示将删除的文件
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RESET='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${RESET}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }

DAYS=30
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --days)    DAYS="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *)         shift ;;
    esac
done

DIRS=("logs" "reports" "results" "artifacts")

log_info "清理 $DAYS 天前的文件..."
[ "$DRY_RUN" = true ] && log_warn "试运行模式 — 不会实际删除"

TOTAL=0
for dir in "${DIRS[@]}"; do
    target="$FRAMEWORK_ROOT/$dir"
    if [ ! -d "$target" ]; then
        continue
    fi

    if [ "$DRY_RUN" = true ]; then
        COUNT=$(find "$target" -type f -mtime +"$DAYS" 2>/dev/null | wc -l)
        log_info "$dir: 将清理 $COUNT 个文件"
        find "$target" -type f -mtime +"$DAYS" -print 2>/dev/null || true
    else
        COUNT=$(find "$target" -type f -mtime +"$DAYS" -delete -print 2>/dev/null | wc -l)
        log_info "$dir: 已清理 $COUNT 个文件"
    fi
    TOTAL=$((TOTAL + COUNT))
done

log_info "清理完成: 共 $TOTAL 个文件"
