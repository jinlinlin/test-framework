#!/usr/bin/env bash
# =============================================================================
# 部署脚本 — 部署被测系统（支持 Docker / K8s / 裸机）
#
# 用法：./deploy.sh [--mode docker|k8s|bare] [--config FILE]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

GREEN='\033[0;32m'; RED='\033[0;31m'; RESET='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

MODE="docker"
CONFIG=""
IMAGE_TAG="latest"

while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)   MODE="$2"; shift 2 ;;
        --config) CONFIG="$2"; shift 2 ;;
        --tag)    IMAGE_TAG="$2"; shift 2 ;;
        *)        shift ;;
    esac
done

deploy_docker() {
    log_info "Docker 部署模式"
    local compose_file="$FRAMEWORK_ROOT/docker/docker-compose.yml"
    if [ -f "$compose_file" ]; then
        log_info "启动 docker-compose..."
        docker compose -f "$compose_file" up -d
        log_info "Docker 服务已启动"
    else
        log_error "docker-compose.yml 不存在"
        exit 1
    fi
}

deploy_k8s() {
    log_info "Kubernetes 部署模式"
    local k8s_dir="$FRAMEWORK_ROOT/kubernetes"
    if command -v kubectl &>/dev/null; then
        log_info "应用 K8s 配置..."
        kubectl apply -f "$k8s_dir/configmap.yaml" 2>/dev/null || true
        kubectl apply -f "$k8s_dir/secret.yaml" 2>/dev/null || true
        kubectl apply -f "$k8s_dir/deployment.yaml"
        kubectl apply -f "$k8s_dir/service.yaml"
        log_info "K8s 资源已创建"
    else
        log_error "kubectl 未安装"
        exit 1
    fi
}

deploy_bare() {
    log_info "裸机部署模式"
    log_info "确保 Python 和 Node.js 已安装"
    bash "$SCRIPT_DIR/setup.sh"
    log_info "裸机部署完成"
}

log_info "=========================================="
log_info "部署模式: $MODE"
log_info "镜像标签: $IMAGE_TAG"
log_info "=========================================="

case $MODE in
    docker) deploy_docker ;;
    k8s)    deploy_k8s ;;
    bare)   deploy_bare ;;
    *)      log_error "不支持的部署模式: $MODE"; exit 1 ;;
esac
