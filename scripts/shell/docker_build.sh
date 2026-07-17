#!/usr/bin/env bash
# =============================================================================
# Docker 构建脚本 — 构建框架 Docker 镜像
#
# 用法：./docker_build.sh [--tag TAG] [--push]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

GREEN='\033[0;32m'; RED='\033[0;31m'; RESET='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

TAG="test-framework:latest"
PUSH=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --tag)  TAG="$2"; shift 2 ;;
        --push) PUSH=true; shift ;;
        *)      shift ;;
    esac
done

log_info "构建 Docker 镜像: $TAG"

DOCKERFILE="$FRAMEWORK_ROOT/docker/Dockerfile"
if [ ! -f "$DOCKERFILE" ]; then
    log_error "Dockerfile 不存在: $DOCKERFILE"
    exit 1
fi

docker build \
    -t "$TAG" \
    -f "$DOCKERFILE" \
    "$FRAMEWORK_ROOT"

log_info "镜像构建完成: $TAG"

if [ "$PUSH" = true ]; then
    log_info "推送镜像: $TAG"
    docker push "$TAG"
    log_info "镜像推送完成"
fi

# 输出镜像信息
log_info "镜像大小: $(docker image inspect "$TAG" --format='{{.Size}}' 2>/dev/null | awk '{printf "%.1f MB", $1/1024/1024}' || echo 'N/A')"
