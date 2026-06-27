#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# build-apk.sh — 构建 PDA APK 并复制到 Web 下载目录
# 用法:
#   ./build-apk.sh              # 仅复制已有 APK（不构建）
#   ./build-apk.sh --build      # 先构建再复制
#   ./build-apk.sh --build release  # 构建 release 变体（默认）
#   ./build-apk.sh --build debug    # 构建 debug 变体
# ─────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ── 解析参数 ──
DO_BUILD=false
BUILD_VARIANT="release"
for arg in "$@"; do
  case "$arg" in
    --build) DO_BUILD=true ;;
    release|debug) BUILD_VARIANT="$arg" ;;
    --help|-h)
      echo "用法: $0 [--build] [release|debug]"
      exit 0
      ;;
  esac
done

# ── 读取版本号 ──
if [ ! -f "pda/package.json" ]; then
  log_err "未找到 pda/package.json"
  exit 1
fi

APP_VERSION=$(python3 -c "import json; print(json.load(open('pda/package.json'))['version'])")
APK_NAME="smes-pda.${APP_VERSION}.apk"
log_info "PDA 版本: ${APP_VERSION}"
log_info "APK 文件名: ${APK_NAME}"

# ── 构建 APK（可选） ──
if [ "$DO_BUILD" = true ]; then
  log_info "开始构建 APK (${BUILD_VARIANT})..."

  if [ ! -f "pda/android/gradlew" ]; then
    log_err "未找到 pda/android/gradlew，请先执行 npx expo prebuild"
    exit 1
  fi

  cd pda/android
  if [ "$BUILD_VARIANT" = "release" ]; then
    ./gradlew assembleRelease
    APK_SRC="app/build/outputs/apk/release/app-release.apk"
  else
    ./gradlew assembleDebug
    APK_SRC="app/build/outputs/apk/debug/app-debug.apk"
  fi
  cd ../..

  if [ ! -f "$APK_SRC" ]; then
    log_err "构建失败：未找到 $APK_SRC"
    exit 1
  fi
  log_ok "APK 构建完成"
else
  # 不构建，直接从默认位置找已构建的 APK
  if [ "$BUILD_VARIANT" = "release" ]; then
    APK_SRC="pda/android/app/build/outputs/apk/release/app-release.apk"
  else
    APK_SRC="pda/android/app/build/outputs/apk/debug/app-debug.apk"
  fi

  if [ ! -f "$APK_SRC" ]; then
    log_warn "未找到已构建的 APK: ${APK_SRC}"
    log_warn "将使用 web/public/apk/ 中已有的文件（如有）"
    APK_SRC=""
  fi
fi

# ── 复制到 web/public/apk/ ──
if [ -n "$APK_SRC" ] && [ -f "$APK_SRC" ]; then
  mkdir -p web/public/apk
  cp "$APK_SRC" "web/public/apk/${APK_NAME}"
  log_ok "已复制到 web/public/apk/${APK_NAME}  ($(du -h web/public/apk/${APK_NAME} | cut -f1))"
elif [ -f "web/public/apk/${APK_NAME}" ]; then
  log_info "web/public/apk/${APK_NAME} 已存在，跳过复制"
else
  log_warn "没有任何 APK 可复制到 web/public/apk/"
fi

# ── 复制到 web/dist/apk/（生产构建目录） ──
if [ -d "web/dist" ]; then
  if [ -n "$APK_SRC" ] && [ -f "$APK_SRC" ]; then
    mkdir -p web/dist/apk
    cp "$APK_SRC" "web/dist/apk/${APK_NAME}"
    log_ok "已复制到 web/dist/apk/${APK_NAME}  ($(du -h web/dist/apk/${APK_NAME} | cut -f1))"
  elif [ -f "web/dist/apk/${APK_NAME}" ]; then
    log_info "web/dist/apk/${APK_NAME} 已存在，跳过复制"
  else
    log_warn "没有任何 APK 可复制到 web/dist/apk/"
  fi
else
  log_warn "web/dist/ 不存在（尚未执行前端构建），跳过 dist 复制"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  完成${NC}"
echo -e "${GREEN}  APK: ${APK_NAME}${NC}"
echo -e "${GREEN}  版本: ${APP_VERSION}${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
