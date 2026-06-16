# 智能物料架管理系统 (Smart Consumable Shelf - SMES)

## 项目概述

基于 LED 智能料架 + Modbus TCP + XR 点料机的电子标签发料管理系统。
实现 SMT 车间物料从入库到出库的全流程数字化管理。

## 核心功能

- **FIFO 尾数优先出库**：优先清空尾数盘，减少整盘退库
- **LED 亮灯指引**：绿色亮灯指引拣料，红色亮灯提示异常
- **XR 点料机集成**：支持多型号 XR 点料机数据上报
- **智能条码识别**：多格式模糊匹配，替代硬编码解析
- **OCR 文字识别**：PaddleOCR 开源引擎，物料标签文字识别、物料编码自动提取
- **BOM 管理**：Excel BOM 导入，自动生成发料单
- **库存跟踪**：实时监控物料在货架上的状态变化

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                      PC Web 前端                         │
│              React 18 + Vite + Ant Design 5              │
│              (管理界面、报表、配置)                        │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/REST API
┌──────────────────────▼──────────────────────────────────┐
│                    FastAPI 后端                           │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  API 路由层  │  │  业务逻辑层   │  │  硬件抽象层   │   │
│  │ (认证/物料/  │  │ (FIFO/LED/   │  │ (AMKN8702G/  │   │
│  │  出入库/库存) │  │  XR/条码)    │  │  AMKN7141)   │   │
│  └─────────────┘  └──────────────┘  └──────────────┘   │
│                         │                                │
│                  ┌──────▼──────┐                         │
│                  │ SQLAlchemy  │                         │
│                  └──────┬──────┘                         │
│                         │                                │
│                  ┌──────▼──────┐                         │
│                  │ PostgreSQL  │                         │
│                  └─────────────┘                         │
└──────────────────────┬──────────────────────────────────┘
                       │ Modbus TCP
┌──────────────────────▼──────────────────────────────────┐
│              AMKN8702G 主控板 (TCP:502)                  │
│  ┌──────────────────┐  ┌──────────────────┐             │
│  │ COM1 → A面灯板   │  │ COM2 → B面灯板   │             │
│  │ (站号 1-63)      │  │ (站号 64-126)    │             │
│  └────────┬─────────┘  └────────┬─────────┘             │
│           │                     │                        │
│    ┌──────▼──────┐      ┌──────▼──────┐                 │
│    │AMKN7141-CHXX │      │AMKN7141-CHXX │                 │
│    │ Modbus RTU  │      │ Modbus RTU  │                 │
│    │ 38400bps    │      │ 38400bps    │                 │
│    └─────────────┘      └─────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 16+
- Docker & Docker Compose (可选)

### 后端启动

```bash
# 1. 克隆项目
cd ComsumableManager

# 2. 创建虚拟环境
cd backend
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 设置数据库连接
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/smes"

# 5. 初始化数据库
alembic upgrade head

# 6. 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Docker 启动（推荐）

```bash
# 1. 设置环境变量
export PG_PASSWORD=your_secure_password

# 2. 启动所有服务
docker-compose up -d

# 3. 初始化数据库
docker exec -it consumable-shelf-backend python -m alembic upgrade head

# 4. 访问服务
# 后端 API: http://localhost:8080
# pgAdmin:  http://localhost:5050
#   账号: admin@smes.local / admin
#   添加服务器: 主机=db, 端口=5432, 数据库=smes, 用户=postgres
```

### PC Web 前端启动

```bash
cd web
npm install
npm run dev
# 访问: http://localhost:5173
```

### PDA 端启动

```bash
cd pda
./gradlew assembleDebug
# 通过 ADB 安装到 Android 设备
adb install app/build/outputs/apk/debug/app-debug.apk
```

## 开发计划

### Phase 1: 基础架构 (已完成 ✅)
- [x] Monorepo 项目结构搭建
- [x] FastAPI 后端框架
- [x] PostgreSQL 数据库设计
- [x] 硬件抽象层 (Modbus TCP + RTU)
- [x] 智能条码识别引擎
- [x] PC Web 前端 (React 18 + Ant Design 5)
- [x] PDA 端 (Kotlin + Jetpack Compose)

### Phase 2: 核心业务逻辑 (进行中 🚧)
- [ ] FIFO 尾数优先算法完善
- [ ] LED 亮灯控制协议实现
- [ ] XR 点料机数据对接
- [ ] 出入库业务流程联调
- [ ] 防呆校验机制

### Phase 3: 前端完善 (计划中 📋)
- [ ] PC Web 全部页面开发
- [ ] PDA 扫码入库/出库功能
- [ ] 报表统计页面
- [ ] 用户管理权限

### Phase 4: 部署上线 (计划中 📋)
- [ ] 硬件联调测试
- [ ] 性能优化
- [ ] 生产环境部署
- [ ] 用户培训

## 硬件集成

### AMKN8702G 主控板

- **通信协议**: Modbus TCP
- **端口**: 502
- **站号**: 200（固定）
- **COM1**: A面灯板，TCP站号 1-63
- **COM2**: B面灯板，TCP站号 64-126

### LED 控制 (AMKN7141-CHXX)

- **协议**: Modbus RTU, 38400bps, 8N1
- **协议2**: 推荐，每个LED占4个线圈
- **地址**: 10000 + 4*(n-1)
  - LEDnG = 10000 + 4*(n-1)
  - LEDnR = 10000 + 4*(n-1) + 1
  - LEDnB = 10000 + 4*(n-1) + 2
  - LEDnControl = 10000 + 4*(n-1) + 3

### 储位状态读取

- **A面**: 数字量输入 0x03E8-0x07CF (1000-1999)
- **B面**: 数字量输入 0x07D0-0x0BB7 (2000-2999)

## API 文档

启动后端后访问：`http://localhost:8080/docs`

主要端点：
- `POST /api/auth/login` - 用户登录
- `GET /api/materials` - 物料列表
- `POST /api/receipt` - 扫码入库
- `POST /api/issue` - 创建发料单
- `GET /api/inventory` - 库存查询
- `POST /api/xr/upload` - XR点料机数据上报
- `POST /api/bom/upload` - BOM Excel 上传

## 项目结构

```
ComsumableManager/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/               # API 路由
│   │   ├── hal/               # 硬件抽象层
│   │   │   ├── modbus.py      # Modbus TCP 协议
│   │   │   └── modbus_tcp.py  # 完整 Modbus 实现
│   │   ├── models/            # 数据库模型
│   │   ├── schemas/           # Pydantic Schema
│   │   ├── services/          # 业务逻辑
│   │   │   ├── fifo_service.py
│   │   │   ├── led_service.py
│   │   │   └── xr_service.py
│   │   └── utils/             # 工具函数
│   │       ├── barcode.py     # 智能条码识别
│   │       └── ocr.py         # PaddleOCR 文字识别（懒加载）
│   ├── alembic/               # 数据库迁移
│   ├── Dockerfile
│   └── requirements.txt
├── web/                       # PC Web 前端
│   ├── src/
│   │   ├── api/               # API 客户端
│   │   ├── components/        # UI 组件
│   │   ├── pages/             # 页面组件
│   │   └── store/             # 状态管理
│   ├── package.json
│   └── vite.config.ts
├── pda/                       # PDA 原生端 (Kotlin)
│   ├── app/
│   │   ├── src/main/java/com/smes/pda/
│   │   │   ├── ui/
│   │   │   │   ├── MainActivity.kt
│   │   │   │   └── theme/
│   │   │   └── ConsumableShelfApp.kt
│   │   └── build.gradle.kts
│   ├── gradle/
│   └── settings.gradle.kts
├── docs/                      # 文档
│   ├── Arch/                  # 硬件协议文档
│   └── 02.系统设计_*.md       # 系统设计文档
├── docker-compose.yml         # Docker 编排
└── README.md                  # 项目文档
```

## 注意事项

1. **硬件联调**：需要现场测试 Modbus TCP 连接和 LED 控制
2. **条码规则**：当前使用智能识别，实际使用时需根据物料条码优化
3. **权限管理**：初期所有用户都是管理员，后续按需添加角色
4. **数据库备份**：生产环境需配置定期备份

## 联系方式

如有问题，请联系项目负责人。
