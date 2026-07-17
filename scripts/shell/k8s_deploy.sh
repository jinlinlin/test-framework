#!/usr/bin/env bash
# =============================================================================
# K8s 部署脚本 — 部署到 Kubernetes 集群
#
# 用法：./k8s_deploy.sh [--namespace NS] [--apply | --delete]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

GREEN='\033[0;32m'; RED='\033[0;31m'; RESET='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

NAMESPACE="default"
ACTION="apply"

while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace) NAMESPACE="$2"; shift 2 ;;
        --apply)     ACTION="apply"; shift ;;
        --delete)    ACTION="delete"; shift ;;
        *)           shift ;;
    esac
done

K8S_DIR="$FRAMEWORK_ROOT/kubernetes"

if ! command -v kubectl &>/dev/null; then
    log_error "kubectl 未安装"
    exit 1
fi

log_info "K8s $ACTION (namespace: $NAMESPACE)"

# 按顺序操作
RESOURCES=("configmap.yaml" "secret.yaml" "deployment.yaml" "service.yaml")

for resource in "${RESOURCES[@]}"; do
    local_file="$K8S_DIR/$resource"
    if [ -f "$local_file" ]; then
        log_info "kubectl $ACTION -f $resource (namespace: $NAMESPACE)"
        kubectl "$ACTION" -f "$local_file" -n "$NAMESPACE" 2>/dev/null || {
            log_error "$ACTION $resource 失败"
        }
    else
        log_error "文件不存在: $local_file"
    fi
done

log_info "K8s $ACTION 完成"

if [ "$ACTION" = "apply" ]; then
    log_info "等待 Pod 就绪..."
    kubectl wait --for=condition=ready pod -l app=test-framework -n "$NAMESPACE" --timeout=120s 2>/dev/null || true
    kubectl get pods -n "$NAMESPACE" -l app=test-framework
fi
