# 智能物料架管理系统

## API 接口技术文档

**`/api/XR/upload`**

---

文档版本: V1.0  
发布日期: 2026-06-17  
文档密级: 内部使用  

## 文档信息

| 文档名称 | 智能物料架管理系统 - XR点料数据上传接口文档 |
| --- | --- |
| 接口路径 | POST /api/XR/upload |
| 文档版本 | V1.0 |
| 发布日期 | 2026-06-17 |
| 密级 | 内部使用 |
| 接收方 | 供应商技术团队 |
| 编制单位 | 智能物料架管理系统项目组 |

## 修订记录

| 版本 | 日期 | 修订内容 | 修订人 |
| --- | --- | --- | --- |
| V1.0 | 2026-06-17 | 初始版本，规范 | — |

## 接口概述

### 接口说明

本接口用于 XR 点料机（X-Ray Point Counter）完成点料后，将料盘数据上传至智能物料架管理系统。系统接收数据后，将创建 XR 批次记录，用于后续的库存匹配与回库操作。

### 接口基本信息

| 接口名称 | XR点料数据上传 |
| --- | --- |
| 接口路径 | /api/XR/upload |
| 请求方法 | POST |
| Content-Type | application/json |
| 接口版本 | v1.0.0 |
| 所属模块 | XR Point Counter（XR点料管理） |
| 接口描述 | 处理 XR 点料机数据上传，创建 XR 批次记录 |

### 接口URL（IP 要求可被配置）

`POST http://服务器ID/api/XR/upload`

### 认证方式

本接口不需要 Token 认证。

## 请求参数

### 请求头 (Request Headers)

| Header名称 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| Content-Type | string | 是 | 固定值: application/json |
| Authorization | string | 是 | Bearer Token认证，格式: Bearer &lt;token&gt; |

### 请求体 (Request Body)

请求体采用 JSON 格式，Schema 定义如下：

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| reel_id | string | 是 | 料盘唯一标识（Reel ID） |
| qty | number | 是 | 点料数量 |

### 请求示例

```http
POST /api/XR/upload HTTP/1.1
Host: [服务器IP] 
Content-Type: application/json
Authorization: Bearer eyJhbG...9...

{
    "reel_id": "R20240617001",
    "qty": 1500
}
```

## 响应参数

### 响应体 (Response Body)

成功响应（HTTP 200）采用 JSON 格式，Schema 定义如下：

| 字段名 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| success | boolean | 是 | 操作是否成功 |
| code | integer | 是 | 业务状态码 |
| message | string | 是 | 响应消息/提示信息 |

### 成功响应示例

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
    "success": true,
    "code": 200,
    "message": "XR批次创建成功"
}
```

### 错误响应示例

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json

{
    "detail": [
        {
            "loc": ["body", "reel_id"],
            "msg": "field required",
            "type": "value_error.missing"
        }
    ]
}
```

## 状态码与错误码

### HTTP 状态码

| 状态码 | 含义 | 说明 |
| --- | --- | --- |
| 200 | OK | 请求成功，XR批次数据已接收并处理 |
| 401 | Unauthorized | 未授权，Token无效或已过期 |
| 422 | Validation Error | 请求参数校验失败，请检查请求体格式及字段 |
| 500 | Internal Server Error | 服务器内部错误，请联系系统管理员 |

### 业务错误码

| 错误码 | 场景 | 处理建议 |
| --- | --- | --- |
| 200 | 成功 | 数据上传成功，XR批次已创建 |
| 422 | 参数校验失败 | 检查 reel_id 和 qty 字段是否存在且格式正确 |
| 401 | 认证失败 | 检查 Authorization 请求头及 Token 有效性 |
