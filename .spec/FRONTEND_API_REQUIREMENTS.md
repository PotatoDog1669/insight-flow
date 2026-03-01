# LexDeepResearch 前端 API 需求清单 (Backend Handoff)

这份文档从**前端视角**梳理了构建 MVP 页面所需要后端实现的所有 API 接口。前端界面已经按此契约完成了所有状态占位与 Mock 交互，后端研发兄弟们可以直接按照本清单实现真实数据返回。

本文档所有的接口前缀约定为：`/api/v1`

---

## 1. 用户与全局设定 (User & Settings)

前端左下角侧边栏（Sidebar）有一块个人档案区域，需要获取当前登录的用户状态。

### 获取当前用户档案
- **请求**：`GET /users/me`
- **响应预期** (200 OK):
  ```json
  {
    "id": "uuid",
    "email": "user@lexmount.com",
    "name": "Lex Researcher",
    "plan": "Free Plan"
  }
  ```

### 更新用户配置 (预留)
- **请求**：`PATCH /users/me/settings`
- **行为**：修改用户偏好的输出语言、默认生成深度等。

---

## 2. 大盘信息源 (Sources)

对应前端 `/sources` 页面。

### 获取信息源大盘列表
- **请求**：`GET /sources`
- **参数**：支持 `?category={category}` (如 blog / open_source / academic / social)，不传则返回全部。
- **UI 强依赖字段** (前端用于渲染卡片)：
  ```json
  [
    {
      "id": "uuid",
      "name": "OpenAI Blog",
      "category": "blog",
      "status": "healthy", // 必须: healthy | error | running
      "last_run": "2 hours ago" // 必须: 友好的相对时间或时间戳
    }
  ]
  ```

### 添加新的信息源
- **请求**：`POST /sources`
- **请求体 (Payload)**：前端表单通过此接口向后端注册新信源。
  ```json
  {
    "category": "blog", // 来源大类
    "name": "某知名技术博客",
    "url": "https://example.com/rss" // 后端基于 url 自行嗅探 collect_method
  }
  ```
- **行为**：后端拿到 payload 后决定用 DeepBrowse 还是 Rss 采集并入库。

---

## 3. 自动化监控任务 (Monitors)

对应前端 `/monitors` 页面。该页面承载了配置信息收集的调度计划。

### 获取所有监控任务列表
- **请求**：`GET /monitors`
- **UI 强依赖字段**：
  ```json
  [
    {
      "id": "uuid",
      "name": "AI Morning Briefing",
      "time_period": "daily",    // enum: daily | weekly | custom
      "custom_schedule": "3",  // 如果 time_period=custom，这里传数字，代表每 X 天执行一次
      "depth": "brief",          // enum: brief | deep
      "sources": ["source_id_1", "source_id_2"], // 关联的信息源 UUID 数组
      "status": "active",        // 用于前端绿点亮暗: active | paused
      "last_run": "2 hours ago"
    }
  ]
  ```

### 创建新任务
- **请求**：`POST /monitors`
- **请求体**：
  ```json
  {
    "name": "Weekly Deep Dive",
    "time_period": "custom",
    "custom_schedule": "7", // 每 7 天
    "depth": "deep",
    "source_ids": ["uuid_1", "uuid_2"]
  }
  ```

### 修改/启停任务
- **请求**：`PATCH /monitors/{monitor_id}`
- **行为**：只传需要修改的字段，例如前端点击卡片底部的开启/暂停按钮时，会发送 `{ "status": "paused" }`。

### 立即运行某任务
- **请求**：`POST /monitors/{monitor_id}/run`
- **行为**：无参数。手动触发后台立即跑一次该监控的 `Collect -> Process -> Render` 流程。

### 彻底删除任务
- **请求**：`DELETE /monitors/{monitor_id}`
- **行为**：永久删除该调度器记录。

---

## 4. 报告广场与检索 (Reports)

对应前端 `/` (Discover 最新速览) 和 `/library` (报告检索库)。

### 分页查询所有已生成的报告
- **请求**：`GET /reports`
- **Query 参数**：
  - `limit=10&page=1`：Discover 首页请求最新 10 条。
  - `time_period=daily&depth=brief`：按类别过滤。
- **响应预期**：
  返回报告列表，包含 `id`, `title`, `time_period`, `depth`, `report_date`, 以及 `tldr` 概览数组（用于简报卡片）。

### 获取文章库可用的过滤元数据
- **请求**：`GET /reports/filters`
- **行为**：给前端 Select 下拉框动态投喂数据。例如当前库里真实有数据的 Category 分类，或者有哪些 `report_date` 年月。

### 查看单份报告完整内容
- **请求**：`GET /reports/{report_id}`
- **行为**：返回单篇深度研发报告，包含 Markdown 内容以及所有关联底层文献（articles）的 Metadata。

---

## 附录：核心交互流程提示

1. **信源采集**：前端不直接操作（触发）全局采集，而是靠后端的定时 Cron 或触发器。前端只查询状态 (`status` 和 `last_run`)。
2. **多用户环境隔离**：所有的 `POST` 和 `GET` `/monitors` & `/reports` 均应自动关联访问 Token 解析出的 `user_id`（信息源 `sources` 为跨租户共享）。
3. **前端枚举值限制**：保证 `depth` 只能在 `['brief', 'deep']` 中流转；`time_period` 在 `['daily', 'weekly', 'custom']` 中流转。
