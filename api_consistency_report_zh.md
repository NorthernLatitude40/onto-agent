# API 接口一致性检查报告

## 概述

前端和后端的 API 接口存在 **32 个不一致问题**：

- 前端调用了 **22 个**后端没有实现的接口
- 后端有 **10 个**接口但前端从未使用
- 没有任何一个接口是完全匹配的（0/33）

## 检查结果详情

### ❌ 前端调用但后端缺失的接口 (22 个)

这些接口在前端被调用，但在后端没有对应的实现：

```
/api/v1/auth/me
/api/v1/auth/wx-login
/api/v1/dashboard/overview
/api/v1/dicts
/api/v1/dicts/device-models
/api/v1/dicts/device-models/brands
/api/v1/inventories/create
/api/v1/inventories/device/add
/api/v1/inventories/device/add-detailed
/api/v1/inventories/device/options
/api/v1/inventories/device/sell
/api/v1/inventories/list
/api/v1/inventories/list?status=1
/api/v1/inventories/search_by_sn
/api/v1/purchases/list
/api/v1/shop/chat
/api/v1/shop/staffs
/api/v1/shop/staffs/accept-invite
/api/v1/shop/staffs/create
/api/v1/shops/current
/api/v1/shops/my-shops
/api/v1/user/default-identity
```

### ⚠️ 后端存在但前端未使用的接口 (10 个)

这些后端接口已经实现，但前端从未调用过：

```
POST /api/v1/create
GET  /api/v1/detail/{order_id}
POST /api/v1/device/add
POST /api/v1/device/add-detailed
GET  /api/v1/device/options
GET  /api/v1/inventory/detail/{target_id}
GET  /api/v1/list
POST /api/v1/refund
GET  /api/v1/search_by_sn
POST /api/v1/status
```

## 问题分析

### 路径结构不一致

前端使用 **基于资源的路径结构**（例如 `/api/v1/inventories/list`），而后端使用 **简单的路径结构**（例如 `/api/v1/list`）。这种差异导致了大部分接口不匹配。

### 后端缺少接口

后端缺少前端期望的许多接口：

- 身份验证相关 (`/auth/me`, `/auth/wx-login`)
- 仪表板 (`/dashboard/overview`)
- 数据字典 (`/dicts`, `/dicts/device-models`)
- 库存管理 (`/inventories/create`, `/inventories/list`)
- 商店和员工管理
- 用户身份 (`/user/default-identity`)

### 后端接口未被使用

后端有一些接口看起来与当前前端无关：

- 订单相关 (`/create`, `/detail/{order_id}`, `/refund`, `/status`)
- 设备管理 (`/device/add`, `/device/add-detailed`, `/device/options`)

## 建议

### 立即行动 (高优先级)

1. **添加缺失的后端接口** 以匹配前端期望
2. **更新前端路径** 以匹配现有后端结构，或者
3. **重构两者** 使用一致的路径结构

### 长期解决方案

1. **实施 API 版本控制** 确保向后兼容性
2. **创建 OpenAPI/Swagger 文档** 用于前端和后端
3. **在 CI/CD 流水线中设置自动化一致性检查**
4. **建立 API 设计指南** 用于路径结构和命名约定

## 技术细节

### 后端分析

- **分析文件**：`./langgraph_workspace/src/api/v1/endpoints/inventory_api.py`
- **发现的总接口数**：10 个
- **HTTP 方法**：POST (6 个), GET (4 个)

### 前端分析

- **扫描目录**：`./miniprogram-1/miniprogram`
- **扫描的文件**：所有 `.ts` 文件
- **发现的 API 调用总数**：33 个
- **默认方法假设**：GET（所有前端调用）

## 检查工具

使用 Python 脚本自动检测这些不一致：

```bash
python langgraph_workspace/api_consistency_check.py
```

该脚本可以定期运行以确保 API 一致性得到维护。

---

**报告生成时间**：2026-10-02
**分析工具**：api_consistency_check.py
**状态**：❌ 不一致（发现 32 个问题）
