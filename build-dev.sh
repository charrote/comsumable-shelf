#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# build-dev.sh — 快速重建并启动前后端开发环境
# 用法: ./build-dev.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${CYAN}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ─────────────────────────────────────────────────────────────
# 1. 环境检查
# ─────────────────────────────────────────────────────────────
log_info "检查基础环境..."

# Python
PYTHON=$(command -v python3 || command -v python || true)
if [ -z "$PYTHON" ]; then
  log_err "未找到 Python3，请先安装"
  exit 1
fi
log_ok "Python: $($PYTHON --version)"

# Node
NODE=$(command -v node || true)
if [ -z "$NODE" ]; then
  log_err "未找到 Node.js，请先安装"
  exit 1
fi
log_ok "Node:   $(node --version)"

# npm
NPM=$(command -v npm || true)
if [ -z "$NPM" ]; then
  log_err "未找到 npm，请先安装"
  exit 1
fi
log_ok "npm:    $(npm --version)"

# Docker (optional — 用于启动 PostgreSQL)
DOCKER=$(command -v docker || true)

# ─────────────────────────────────────────────────────────────
# 2. 依赖安装
# ─────────────────────────────────────────────────────────────
log_info "安装后端依赖 (pip)..."
cd backend
$PYTHON -m pip install -r requirements.txt --quiet 2>&1 | tail -1
log_ok "后端依赖已安装"

cd ../web
log_info "安装前端依赖 (npm)..."
npm install --silent 2>&1 | tail -1
log_ok "前端依赖已安装"
cd ..

# ─────────────────────────────────────────────────────────────
# 3. 确保 PostgreSQL 已启动（优先用 Docker，也支持本地 PG）
# ─────────────────────────────────────────────────────────────
PG_READY=false

# 尝试连接本地 PG（用 psql 或 python 检测）
if command -v psql &>/dev/null; then
  if psql -h localhost -U postgres -d smes -c "SELECT 1;" &>/dev/null 2>&1; then
    PG_READY=true
    log_ok "PostgreSQL (本地) 已就绪"
  fi
fi

if [ "$PG_READY" = false ] && [ -n "$DOCKER" ]; then
  log_info "启动 PostgreSQL (Docker)..."
  docker compose up -d db 2>/dev/null || docker-compose up -d db 2>/dev/null || true
  # 等待 PG 就绪
  for i in $(seq 1 30); do
    if docker exec consumable-shelf-db pg_isready -U postgres &>/dev/null 2>&1; then
      PG_READY=true
      log_ok "PostgreSQL (Docker) 已就绪"
      break
    fi
    sleep 1
  done
fi

if [ "$PG_READY" = false ]; then
  log_err "PostgreSQL 未就绪。请确保 PostgreSQL 在 localhost:5432 上运行。"
  log_err "数据库: smes, 用户: postgres, 密码: postgres"
  log_err "或用 Docker: docker compose up -d db"
  exit 1
fi

# ─────────────────────────────────────────────────────────────
# 4. 杀掉旧进程
# ─────────────────────────────────────────────────────────────
log_info "清理旧进程..."
# 后端 (uvicorn)
lsof -ti:8080 2>/dev/null | xargs kill -9 2>/dev/null || true
# 前端 (vite)
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1
log_ok "旧进程已清理"

# ─────────────────────────────────────────────────────────────
# 5. 启动后端
# ─────────────────────────────────────────────────────────────
log_info "启动后端 (uvicorn) → http://localhost:8080 ..."
cd backend
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/smes" \
HARDWARE_SIMULATION=true \
LOG_LEVEL=info \
nohup "$PYTHON" -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8080 \
  --reload \
  --log-level info \
  > ../.backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# 等待后端就绪
for i in $(seq 1 30); do
  if curl -sf http://localhost:8080/health >/dev/null 2>&1; then
    log_ok "后端已就绪 (PID $BACKEND_PID)"
    break
  fi
  sleep 1
done

# ─────────────────────────────────────────────────────────────
# 6. 启动前端
# ─────────────────────────────────────────────────────────────
log_info "启动前端 (Vite) → http://localhost:5173 ..."
cd web
nohup npx vite --host 0.0.0.0 --port 5173 \
  > ../.frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

sleep 2
log_ok "前端已启动 (PID $FRONTEND_PID)"

# ─────────────────────────────────────────────────────────────
# 7. 显示状态
# ─────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  开发环境已就绪${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "  后端 API: ${CYAN}http://localhost:8080${NC}"
echo -e "   API 文档: ${CYAN}http://localhost:8080/docs${NC}"
echo -e "  前端页面: ${CYAN}http://localhost:5173${NC}"
echo -e "  后端日志: ${CYAN}.backend.log${NC}"
echo -e "  前端日志: ${CYAN}.frontend.log${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "停止: kill $BACKEND_PID $FRONTEND_PID"
echo ""

# ── 等待子进程（按 Ctrl+C 时同时退出前后端）──
trap "log_info '正在关闭...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
