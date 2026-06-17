#!/usr/bin/env bash
set -euo pipefail

# PDA APK 构建 & 部署到 Web 前端
# Usage: ./build-and-copy.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WEB_DIR="$PROJECT_DIR/web"
PDA_DIR="$SCRIPT_DIR"

echo "🔨 Building PDA APK..."
cd "$PDA_DIR"
export JAVA_HOME=/opt/homebrew/opt/openjdk@17
./gradlew assembleDebug

echo "📦 Copying APK to web/public/apk/..."
cp "$PDA_DIR/app/build/outputs/apk/debug/app-debug.apk" "$WEB_DIR/public/apk/"

echo "📐 Building web frontend..."
cd "$WEB_DIR"
npx vite build

echo ""
echo "✅ Done!"
echo "   APK:    $PDA_DIR/app/build/outputs/apk/debug/app-debug.apk"
echo "   Web:    $WEB_DIR/dist/"
echo ""
echo "   To test locally, run: cd $WEB_DIR && npx vite preview"
