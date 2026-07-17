#!/usr/bin/env bash
# =============================================================================
# 备份脚本 — 备份配置和测试结果
#
# 用法：./backup.sh [--output DIR]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

GREEN='\033[0;32m'; RESET='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${RESET} $*"; }

BACKUP_DIR="${1:-$FRAMEWORK_ROOT/backups}"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_NAME="tf_backup_${TIMESTAMP}.tar.gz"

mkdir -p "$BACKUP_DIR"

log_info "开始备份..."
log_info "备份目录: $BACKUP_DIR"
log_info "备份文件: $BACKUP_NAME"

# 备份配置和结果
tar -czf "$BACKUP_DIR/$BACKUP_NAME" \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='.git' \
    -C "$FRAMEWORK_ROOT" \
    config/ \
    results/ \
    reports/ \
    2>/dev/null || true

SIZE=$(du -h "$BACKUP_DIR/$BACKUP_NAME" 2>/dev/null | cut -f1 || echo "unknown")
log_info "备份完成: $BACKUP_NAME ($SIZE)"
