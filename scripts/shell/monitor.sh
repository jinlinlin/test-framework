#!/usr/bin/env bash
# =============================================================================
# 资源监控脚本 — 持续采集系统 CPU/内存/磁盘/网络指标
#
# 用法：./monitor.sh [--interval N] [--output FILE]
#   --interval N   采集间隔（秒，默认 5）
#   --output FILE  输出文件路径
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; RESET='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${RESET} $*"; }

INTERVAL=5
OUTPUT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --interval) INTERVAL="$2"; shift 2 ;;
        --output)   OUTPUT="$2"; shift 2 ;;
        *)          shift ;;
    esac
done

# 输出函数
output_line() {
    local line="$1"
    echo "$line"
    if [ -n "$OUTPUT" ]; then
        echo "$line" >> "$OUTPUT"
    fi
}

# 采集系统指标
collect_metrics() {
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # CPU 使用率
    local cpu_usage="N/A"
    if command -v top &>/dev/null; then
        cpu_usage=$(top -bn1 2>/dev/null | grep "Cpu(s)" | awk '{print $2}' || echo "N/A")
    fi

    # 内存使用
    local mem_total="N/A" mem_used="N/A" mem_pct="N/A"
    if command -v free &>/dev/null; then
        mem_total=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo "N/A")
        mem_used=$(free -m 2>/dev/null | awk '/^Mem:/{print $3}' || echo "N/A")
        mem_pct=$(free 2>/dev/null | awk '/^Mem:/{printf "%.1f", $3/$2*100}' || echo "N/A")
    fi

    # 磁盘使用
    local disk_pct="N/A"
    if command -v df &>/dev/null; then
        disk_pct=$(df -h / 2>/dev/null | awk 'NR==2{print $5}' || echo "N/A")
    fi

    output_line "$timestamp | CPU: ${cpu_usage}% | MEM: ${mem_used}/${mem_total}MB (${mem_pct}%) | DISK: ${disk_pct}"
}

log_info "开始资源监控 (间隔: ${INTERVAL}s)"
log_info "按 Ctrl+C 停止"
echo "-------------------------------------------"

# 写入 CSV 头
if [ -n "$OUTPUT" ]; then
    echo "# Timestamp | CPU | Memory | Disk" > "$OUTPUT"
fi

while true; do
    collect_metrics
    sleep "$INTERVAL"
done
