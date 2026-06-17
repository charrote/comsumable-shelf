# PDA 单元测试任务规划

## 测试目录结构

```
pda/
├── app/src/test/java/com/smes/pda/          # 单元测试
│   ├── data/
│   │   ├── api/
│   │   │   └── ApiServiceTest.kt            # API 服务调用测试
│   │   ├── repository/
│   │   │   ├── AuthRepositoryTest.kt        # 认证仓库测试
│   │   │   ├── ReceiptRepositoryTest.kt     # 入库仓库测试
│   │   │   ├── IssueRepositoryTest.kt       # 出库仓库测试
│   │   │   └── InventoryRepositoryTest.kt   # 库存仓库测试
│   │   └── model/
│   │       └── SerializationTest.kt         # 数据模型序列化测试
│   ├── ui/viewmodel/
│   │   ├── AuthViewModelTest.kt             # 认证 ViewModel 测试
│   │   ├── InboundViewModelTest.kt          # 入库 ViewModel 测试
│   │   ├── OutboundViewModelTest.kt         # 出库 ViewModel 测试
│   │   ├── RestockViewModelTest.kt          # 补料 ViewModel 测试
│   │   └── TrackingViewModelTest.kt         # 跟踪 ViewModel 测试
│   └── data/local/
│       ├── InventoryDaoTest.kt              # Room DAO 测试
│       └── AppDatabaseTest.kt               # 数据库测试
└── app/src/androidTest/java/com/smes/pda/   # 仪器化测试 (UI)
    └── ui/
        ├── MainActivityTest.kt              # 主 Activity 测试
        ├── InboundScreenTest.kt             # 入库界面测试
        └── InboundScreenTest.kt             # 出库界面测试
```

---

## 测试任务清单

### 1. 数据模型序列化测试

| 测试项 | 说明 |
|--------|------|
| `LoginRequest` 序列化 | 验证 username/password 字段正确序列化为 JSON |
| `TokenResponse` 反序列化 | 验证 access_token/token_type/expires_in 正确解析 |
| `ReceiptScanResponse` 反序列化 | 验证 status/action/inventory_pallet_id 等字段 |
| `IssueCalculateResponse` 反序列化 | 验证嵌套的 MaterialCalcResult + PalletSelection 数组 |
| `IssueConfirmPickResponse` 反序列化 | 验证 status/picked_qty/all_picked 等字段 |
| `InventoryResponse` 反序列化 | 验证 pallets 数组 + summary 对象 |
| `TrackingListResponse` 反序列化 | 验证 tracking 料盘列表 |
| `ApiResult.Sealed` 测试 | 验证 Success/Error 两种状态正确实例化 |

### 2. Repository 层测试

#### AuthRepositoryTest
| 测试项 | 说明 |
|--------|------|
| `login 成功` | Mock ApiService 返回 TokenResponse, 验证 token 保存 |
| `login 失败` | Mock ApiService 抛出异常, 验证 ApiResult.Error 返回 |
| `isLoggedIn 有 token` | Mock AuthInterceptor 返回 token, 验证返回 true |
| `isLoggedIn 无 token` | Mock AuthInterceptor 返回 null, 验证返回 false |
| `logout 清除 token` | 验证 clearToken 被调用 |

#### ReceiptRepositoryTest
| 测试项 | 说明 |
|--------|------|
| `scanInbound 成功` | Mock API 返回 ReceiptScanResponse, 验证正确映射 |
| `scanInbound 网络错误` | Mock API 抛出异常, 验证 Error 返回 |
| `createReceipt 成功` | Mock API 返回 ReceiptDetailResponse, 验证 receiptId 正确 |

#### IssueRepositoryTest
| 测试项 | 说明 |
|--------|------|
| `listIssues 成功` | Mock API 返回出库单列表 |
| `listIssues 空列表` | Mock API 返回空列表 |
| `calculate 成功` | Mock API 返回 IssueCalculateResponse, 验证 pallets_selected |
| `calculate 缺料` | Mock API 返回 shortage > 0 的情况 |
| `confirmPick 成功` | Mock API 返回 IssueConfirmPickResponse, 验证 all_picked |
| `confirmPick 已完成` | Mock API 返回 status=completed |

#### InventoryRepositoryTest
| 测试项 | 说明 |
|--------|------|
| `getInventory 成功` | Mock API 返回 InventoryResponse, 验证 pallets 列表 |
| `getInventory 过滤参数` | 验证 customer_id/material_id 参数正确传递 |
| `getTrackingInventory 成功` | Mock API 返回 TrackingListResponse |

### 3. ViewModel 层测试

#### AuthViewModelTest
| 测试项 | 说明 |
|--------|------|
| `初始状态未登录` | 验证 isLoggedIn = false |
| `login 成功 -> 状态更新` | 验证 isLoading 生命周期: false -> true -> false, isLoggedIn = true |
| `login 失败 -> error 设置` | 验证 error 字段被设置为错误信息 |
| `logout -> 重置状态` | 验证 isLoggedIn = false, user = null |
| `clearError -> error 清除` | 验证 error = null |

#### InboundViewModelTest
| 测试项 | 说明 |
|--------|------|
| `initReceipt 成功` | 验证 activeReceiptId 被设置 |
| `scanBarcode 成功` | 验证 lastScanResult 和 scanHistory 更新 |
| `scanBarcode 无 activeReceiptId` | 验证不调用 API |
| `scanBarcode API 失败` | 验证 error 设置, history 不增加 |
| `clearLastScan` | 验证 lastScanResult = null |

#### OutboundViewModelTest
| 测试项 | 说明 |
|--------|------|
| `loadPendingIssues 成功` | 验证 pendingIssues 列表更新 |
| `selectIssue 成功` | 验证 selectedIssue 被设置 |
| `calculate 成功` | 验证 calcResult 包含 pallets_selected |
| `assign 成功` | 验证 assignResult 包含 led_commands |
| `confirmPick 成功` | 验证 confirmResult 状态更新 |
| `confirmPick 全部拣完` | 验证 all_picked = true 的行为 |
| `setOperator` | 验证 operator 字段更新 |

#### RestockViewModelTest
| 测试项 | 说明 |
|--------|------|
| `initRestock 成功` | 验证 activeReceiptId 设置, type=restock |
| `scanBarcode 成功` | 验证 scanHistory 累加 |
| `scanBarcode 重复扫描` | 验证 duplicate_flag 处理 |

#### TrackingViewModelTest
| 测试项 | 说明 |
|--------|------|
| `loadTracking 成功` | 验证 trackingPallets 列表 |
| `loadOnShelfInventory 成功` | 验证 onShelfInventory 更新 |
| `selectTab 切换` | 验证 selectedTab 变化 |
| `加载中状态` | 验证 isLoading 状态正确切换 |

### 4. 本地数据库测试 (Room)

| 测试项 | 说明 |
|--------|------|
| `insertAll / 查询` | 插入 CachedInventory 列表, 验证 getAll 返回 |
| `getByStatus` | 按 status 过滤查询 |
| `clearAll` | 清除所有缓存, 验证查询为空 |
| `deleteById` | 删除单条记录 |
| `重复插入 (REPLACE)` | 相同 pallet_id 插入两次, 验证只有一条 |

### 5. API 服务层测试

| 测试项 | 说明 |
|--------|------|
| `login 请求` | 验证 URL/Method/Body 正确 |
| `Auth header 附加` | 验证有 token 时 Authorization header 存在 |
| `Auth header 无 token` | 验证无 token 时不添加 header |
| `超时处理` | Mock 超时异常, 验证 ApiResult.Error |
| `HTTP 401 处理` | Mock 401 响应, 验证 Error 包含状态码 |
| `HTTP 500 处理` | Mock 500 响应, 验证 Error 消息 |

### 6. UI 仪器化测试 (AndroidTest)

| 测试项 | 说明 |
|--------|------|
| `MainActivity 启动` | 验证首页显示 "智能物料架 PDA" |
| `底部导航切换` | 验证点击 Tab 切换到对应页面 |
| `InboundScreen 输入框` | 验证输入框可输入, 按钮随内容变化 |
| `OutboundScreen 出库单列表` | 验证列表渲染 |
| `SettingsScreen 显示` | 验证设置页面显示服务器地址 |

---

## 测试依赖说明

项目 `build.gradle.kts` 已包含的测试依赖:
```kotlin
testImplementation("junit:junit:4.13.2")
androidTestImplementation("androidx.test.ext:junit:1.1.5")
androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
androidTestImplementation("androidx.compose.ui:ui-test-junit4")
debugImplementation("androidx.compose.ui:ui-test-manifest")
```

需要额外添加的 Mock 依赖:
```kotlin
// MockK (Kotlin Mock 库)
testImplementation("io.mockk:mockk:1.13.9")

// Coroutines 测试
testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")

// Turbine (Flow 测试)
testImplementation("app.cash.turbine:turbine:1.0.0")

// Room 测试
testImplementation("androidx.room:room-testing:2.6.1")
```

---

## 测试运行命令

```bash
# 运行所有单元测试
cd pda
./gradlew testDebugUnitTest

# 运行具体测试类
./gradlew testDebugUnitTest --tests "com.smes.pda.ui.viewmodel.AuthViewModelTest"

# 运行 UI 仪器化测试 (需连接设备/模拟器)
./gradlew connectedDebugAndroidTest

# 查看测试报告
open app/build/reports/tests/testDebugUnitTest/index.html
```

---

## 测试优先级

| 优先级 | 模块 | 原因 |
|--------|------|------|
| P0 | AuthViewModel | 登录是 PDA 入口, 失败则无法使用 |
| P0 | OutboundViewModel | 出库是核心业务流程 |
| P0 | InboundViewModel | 入库是核心业务流程 |
| P1 | IssueRepository, ReceiptRepository | Repository 是业务逻辑枢纽 |
| P1 | ApiService (Auth header) | 所有请求依赖认证 |
| P1 | Serialization | 数据模型正确性影响所有层 |
| P2 | RestockViewModel | 补料是辅助流程 |
| P2 | TrackingViewModel | 查询类功能 |
| P2 | Room DAO | 本地缓存, 离线能力 |
| P3 | UI 仪器化测试 | 集成测试, 可后期补充 |
