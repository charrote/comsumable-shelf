# 智能料架重构 — 操作端（PDA）功能同步排查

> 排查日期: 2026-06-27  
> 排查范围: PDA (React Native/Expo) ↔ Backend (FastAPI) 功能同步状态  
> 排查人: Unified Expert (全栈工程师 + 高级项目经理)

---

## 一、排查结论速览

| 功能模块 | PDA 状态 | 后端 API | 同步程度 | 优先级 |
|---------|---------|----------|---------|--------|
| 入库（收料） | `InboundScreen` | ✅ 完整 | ⚠️ **已同步但有 Bug** | 🔴 高 |
| 出库-按料单 (FIFO+LED) | `OutboundScreen` | ✅ 完整 | ✅ **已同步但有缺陷** | 🟡 中 |
| 出库-单独出料 | `OutboundScreen` | ✅ 完整 | ✅ **已同步** | ✅ |
| 智能上架（传感器检测） | `ShelvingScreen` | ✅ 完整 | ✅ **已同步** | ✅ |
| 手动上架（扫码储位） | `ShelvingScreen` | ✅ 完整 | ✅ **已同步** | ✅ |
| **落架（解除绑定）** | ❌ **未实现** | ✅ 支持 | ❌ **关键缺口** | 🔴 **高** |
| 补料上架 (Restock) | ⚠️ 孤儿代码 | ✅ 支持 | ⚠️ **未注册到导航** | 🟡 中 |
| 灯测试 | ❌ 无此需求 | ✅ | ✅ （PC端功能） | — |

---

## 二、各功能详细排查

---

### 2.1 入库（收料）— `InboundScreen.tsx`

#### 已同步的功能
- 创建/选择草稿收料单
- 扫码预览 + 确认两步式流程（`scan-preview` → `scan`）
- 置信度展示（百分比 + 颜色编码 + 进度条）
- 物料候选列表选择（低置信度时）
- 新料号创建
- 手工录入（非条码物料）
- 可编辑字段：物料名称、规格、批次号、生产周期
- 取消入库明细
- 摄像头扫码

#### 🔴 Bug: 手工录入导致运行时崩溃

**位置**: `InboundScreen.tsx` 第 224 行

```typescript
// ❌ 问题代码：
setHistory((prev) => [result, ...prev])
//    ^^^^^^^^^^ 这个 state 从未声明，调用即崩溃
```

**原因**: 从 `RestockScreen.tsx` 复制代码时遗漏了 state 声明。`RestockScreen` 有正确写法：

```typescript
// ✅ 正确写法（RestockScreen.tsx line 22）：
const [history, setHistory] = useState<ReceiptScanResponse[]>([])
```

**影响**: 手工录入成功后会触发运行时崩溃。

---

### 2.2 出库（扫码出库）— `OutboundScreen.tsx`

#### 2.2.1 按料单出库（BOM Picking）

**流程已同步**: `选择发料单 → FIFO 计算 → LED 亮灯 → 扫码取料`

具体已实现：
| 步骤 | API | PDA 实现 | 状态 |
|------|-----|---------|------|
| 获取发料单列表 | `GET /issues` | ✅ 列表展示 | ✅ |
| 查看发料单详情 | `GET /issues/{id}` | ✅ 物料明细 | ✅ |
| FIFO 计算 | `POST /issues/{id}/calculate` | ✅ 结果显示（需求/可用/短缺） | ✅ |
| LED 亮灯 | `POST /issues/{id}/assign` | ✅ **已对接料架亮灯** | ✅ |
| 确认拣料 | `POST /issues/{id}/confirm-pick` | ✅ 结果显示 | ✅ |
| 全部完成检测 | — | ✅ all_picked 判断 | ✅ |

#### 🟡 缺陷: confirmPick 固定传第一个 reel_id

**位置**: `OutboundScreen.tsx` 第 131 行

```typescript
// ❌ 总取第一个料的第一个 reel_id，与扫描条码无关
const firstReelId = calcResult.materials[0]?.reels_selected[0]?.reel_id

// 调用时：
await confirmPickApi(selectedIssue.id, {
  barcode: pickBarcode.trim(),   // ← 扫描的条码
  reel_id: firstReelId,          // ← 但 reel_id 是固定的！
  operator,
})
```

**影响**: 后端收到的 `barcode` 和 `reel_id` 可能不匹配。虽然后端可能按 barcode 重新解析，但这会造成歧义。

#### 2.2.2 单独出料（Direct Outbound）

**流程**: `扫描料盘 → 输入数量 → 确认出库 (release_slot: true)`

| 步骤 | API | PDA 实现 | 状态 |
|------|-----|---------|------|
| 扫描料盘 | `POST /inventory/scan-reel` | ✅ | ✅ |
| 直接出库 | `POST /inventory/reels/{id}/direct-out` | ✅ 含 release_slot | ✅ |
| 结果显示 | — | ✅ 出库前后数量 + 储位释放 | ✅ |

---

### 2.3 上架（料盘上架）— `ShelvingScreen.tsx` ✅

**这是 PDA 中与智能料架集成最深入的页面，两种模式均已完整实现。**

#### 模式 A: 智能料架模式

**流程**: `选择料架 → 扫描料盘 → 传感器轮询 → 放入即识别 → 确认绑定`

| 步骤 | API | 实现细节 | 状态 |
|------|-----|---------|------|
| 获取料架列表 | `GET /shelves` | 横向 chip 选择器 | ✅ |
| 扫描料盘条码 | `POST /shelving/scan` | 键盘/摄像头 | ✅ |
| 料盘信息展示 | — | Reel ID、物料编码/名称、数量 | ✅ |
| 已绑定检测 | — | 显示已上架信息，阻止重复操作 | ✅ |
| 传感器轮询 | `GET /shelves/{id}/slots/state` | **1.5s 间隔**，检测 `false→true` 变化 | ✅ |
| 储位自动识别 | — | 对比前后状态差，识别放入的储位 | ✅ |
| 确认绑定 | `POST /shelving/bind` | 保存上架 | ✅ |

**轮询核心逻辑**（ShelvingScreen.tsx line 85-111）：
```typescript
// 每 1.5s 查询传感器状态
pollingRef.current = setInterval(async () => {
  const sr = await getSlotStatesApi(shelfId)
  // 对比前后状态，检测 false→true 的变化
  for (const s of sr.slots) {
    const was = prev.get(s.slot_id)
    if (was === false && s.has_material && 
        (s.bound_reel_id == null || s.bound_reel_id === rid)) {
      setDetectedSlot(s)  // 自动识别储位
      break
    }
  }
}, 1500)
```

#### 模式 B: 手动上架模式

**流程**: `扫描料盘 → 扫描储位条码 → 确认绑定`

| 步骤 | API | 实现细节 | 状态 |
|------|-----|---------|------|
| 扫描料盘 | `POST /shelving/scan` | 同智能模式 | ✅ |
| 扫描储位条码 | `POST /shelving/scan-slot` | 格式如 A1A05 | ✅ |
| 占用检查 | — | status=occupied 时告警 | ✅ |
| 自动关联料架 | — | 从储位反查料架 | ✅ |
| 确认绑定 | `POST /shelving/bind` | 保存上架 | ✅ |

---

### 2.4 🔴 落架（解除绑定）— 未实现 — 关键缺口

**现状**: PDA **没有任何落架功能的入口或界面**。

#### 后端已具备的能力

| API | 方法 | 用途 | PDA 是否调用 |
|-----|------|------|-------------|
| `/api/inventory/reels/{reel_id}/direct-out` | POST | 直接出库 + 释放储位 | ✅ 用于出库 |
| `/api/inventory/{reel_id}` | PUT | 更新库存（可清空 shelf_slot_id） | ❌ **未导出** |

#### 建议落架流程（当前缺失）

```
┌─ 进入落架 ─────────────────────────────────────────────┐
│  方式A: 扫描储位条码 → 显示当前料盘信息 → 确认落架      │
│  方式B: 扫描料盘条码 → 显示储位信息 → 确认落架          │
│                                                         │
│  确认后:                                                 │
│  1. PUT /api/inventory/{reel_id} → shelf_slot_id = null │
│  2. 记录 ShelfSlotEvent (event_type = "released")       │
│  3. 库存状态变更 (on_shelf → tracking / exhausted)      │
│  4. 可选: 发送 LED 灭灯指令                              │
└─────────────────────────────────────────────────────────┘
```

#### 需要补充的 PDA 代码

1. **新增 API** `api/index.ts`:
   ```typescript
   export async function updateInventoryApi(reelId: number, data: {
     shelf_slot_id?: number | null
     status?: string
     operator?: string
   }): Promise<any> {
     const res = await api.put(`/inventory/${reelId}`, data)
     return res.data
   }
   ```

2. **新增页面** `UnshelvingScreen.tsx` 或将其并入 `ShelvingScreen` 的第三种模式

---

### 2.5 ⚠️ 补料上架（Restock）— 已实现但无法访问

`RestockScreen.tsx` 是完整的页面：
- 创建补料单（`createReceiptApi({ type: 'restock' })`）
- 扫码补料入库
- 扫描历史记录

**但它在 `App.tsx` 中未被注册**：
```typescript
// App.tsx — 已注册的 5 个 Tab：
// Home, Inbound, Shelving, Outbound, Tracking
// RestockScreen 从未 import，也没有 Tab.Screen
```

**建议**：确认是否需要此功能。若需要则注册到导航；若不需要则删除文件。

---

### 2.6 灯测试 — 未在 PDA 实现（合理）

| 端 | 实现 | 说明 |
|---|------|------|
| 后端 | `POST /api/shelves/{id}/rack-test` | ✅ 完整 |
| Web 端 | `ShelfManagementPage.tsx` 的"灯测试"按钮 | ✅ |
| PDA | ❌ 无此功能 | **合理**，灯测试是 PC 端管理/诊断功能 |

**灯测试是管理员/硬件工程师的 PC 端工具**，PDA 专注仓储操作流程，不需要此功能。

---

## 三、数据流全图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PDA (操作端)                                │
│                                                                     │
│  InboundScreen     ShelvingScreen     OutboundScreen                │
│  ┌──────────┐     ┌───────────┐     ┌───────────┐                  │
│  │ 收料入库  │     │ 料盘上架   │     │ 扫码出库   │                  │
│  │          │     │ ┌───────┐ │     │ ┌───────┐ │                  │
│  │ 扫码预览  │     │ │智能料架│ │     │ │按料单  │ │                  │
│  │ →确认    │     │ │传感器  │ │     │ │FIFO   │ │                  │
│  │ 手工录入  │     │ │轮询检测 │ │     │ │LED亮灯│ │                  │
│  │ 取消明细  │     │ └───────┘ │     │ │扫码取料│ │                  │
│  └────┬─────┘     │ ┌───────┐ │     │ └───────┘ │                  │
│       │           │ │手动上架│ │     │ ┌───────┐ │                  │
│       │           │ │扫码储位│ │     │ │单独出料│ │                  │
│       │           │ └───────┘ │     │ │直接出库│ │                  │
│       │           └─────┬─────┘     │ └───────┘ │                  │
│       │                 │           │           │                  │
│       ▼                 ▼           ▼           ▼                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    HTTP API (Axios)                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Backend (FastAPI)                             │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Receipt  │  │ Shelving │  │  Issue   │  │   RackApiClient  │   │
│  │ Service  │  │ Service  │  │  Service │  │  (HTTP to 硬件)  │   │
│  │ 入库逻辑  │  │ 上架/绑定 │  │ FIFO+出库│  │  LED/Test/状态  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │             │             │                  │             │
│       ▼             ▼             ▼                  ▼             │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                     Database (PostgreSQL)                 │      │
│  │  inventory_reels / shelf_slots / led_commands / ...      │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                     ┌─────────────────────┐
                     │   物理智能料架硬件    │
                     │   (HTTP API 服务)    │
                     │   LED 灯控 / 传感器  │
                     └─────────────────────┘
```

---

## 四、待修复/补充事项清单

### 🔴 优先级 P0 — 影响使用

| # | 位置 | 问题 | 影响 | 建议修复 |
|---|------|------|------|---------|
| 1 | `InboundScreen.tsx:224` | `setHistory` 未声明 state | 手工入库时**运行时崩溃** | 添加 `const [history, setHistory] = useState<ReceiptScanResponse[]>([])` 或移除该行 |

### 🟡 优先级 P1 — 功能不完整

| # | 位置 | 问题 | 影响 | 建议修复 |
|---|------|------|------|---------|
| 2 | `OutboundScreen.tsx:131` | `confirmPick` 固定传第一个 reel_id | 扫描条码与实际扣减不一致 | 调用后端时传 `reel_id: undefined` 让后端自行解析，或根据扫描条码匹配正确的 reel |
| 3 | 全系统缺失 | **落架功能**（Unshelving） | 无法将料盘从储位解除绑定 | 新建 `UnshelvingScreen` 或并入 `ShelvingScreen` |

### 🔵 优先级 P2 — 清理/优化

| # | 位置 | 问题 | 建议 |
|---|------|------|------|
| 4 | `RestockScreen.tsx` | 完整页面但未注册到导航 | 确认是否需要：需要则注册为 Tab 或子页面；不需要则删除 |
| 5 | `pda/src/api/index.ts` | 缺少 `updateInventoryApi` | 若实现落架功能需补充 `PUT /inventory/{reel_id}` 的 API 导出 |

---

## 五、PDA ↔ Web 端功能分布说明

了解两端分工有助于判断哪些该补、哪些不该补：

| 功能 | 最佳操作端 | 原因 |
|------|-----------|------|
| 收料入库 | **PDA** | 扫码便捷，现场操作 |
| 上架（智能/手动） | **PDA** | 需要现场放料，传感器交互 |
| 按料单出库 + LED 亮灯 | **PDA** | 现场扫码取料，看灯指引 |
| 单独出料 | **PDA** | 现场扫码 |
| **落架** | **PDA** （缺失） | 现场操作，从储位取走料盘时 |
| 补料上架 | **PDA** （孤儿） | XR 点料后现场上架 |
| 灯测试 | **Web 端** | 管理员诊断，无需 PDA |
| 料架 CRUD | **Web 端** | 管理配置 |
| 储位管理 | **Web 端** | 管理配置 |
| BOM 管理 | **Web 端** | 数据维护 |
| 报表统计 | **Web 端** | 数据分析 |
| 条码规则定义 | **Web 端** | 配置管理 |
| 系统设置 | **Web 端** | 配置管理 |

**结论**: 上架（智能+手动）和出库（含 LED 亮灯）是 PDA 的**核心差异化功能**，已正确实现在 PDA 端。**落架**是唯一缺失的关键操作流程，建议优先补齐。

---

## 六、附录：关键文件索引

| 文件 | 行数 | 说明 |
|------|------|------|
| `pda/src/App.tsx` | 169 | 导航配置，5 个 Tab，RestockScreen 未注册 |
| `pda/src/screens/InboundScreen.tsx` | 809 | 入库扫码页面，⚠️ 第 224 行 Bug |
| `pda/src/screens/ShelvingScreen.tsx` | 505 | 上架页面（智能+手动），✅ 最完善 |
| `pda/src/screens/OutboundScreen.tsx` | 620 | 出库页面（按料单+单独），⚠️ 第 131 行缺陷 |
| `pda/src/screens/RestockScreen.tsx` | 177 | 补料上架，⚠️ 未注册的孤儿代码 |
| `pda/src/api/index.ts` | 242 | 全部 API 导出，❌ 缺少 `updateInventoryApi` |
| `backend/app/api/shelves.py` | ~320 | 料架 CRUD + 灯测试端点 |
| `backend/app/api/issue.py` | ~150 | 出库 + LED 亮灯端点 |
| `backend/app/api/shelving.py` | ~80 | 上架绑定端点 |
| `backend/app/services/rack_api_client.py` | ~320 | 料架硬件 HTTP 通信客户端 |
| `backend/app/services/led_service.py` | ~120 | LED 指令后台工作器 |
| `web/src/pages/ShelfManagementPage.tsx` | ~400 | Web 端料架管理 + 灯测试 |
