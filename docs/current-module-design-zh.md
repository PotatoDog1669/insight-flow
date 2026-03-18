# 当前模块设计实现说明

本文基于当前仓库实现梳理侧边栏 6 个模块的设计与已实现功能，覆盖：

- 报告
- 任务
- 归档
- 信息源
- 模型配置
- 输出配置

说明原则：

- 只描述当前代码里已经存在的设计和行为。
- 对前端已暴露、但后端仍有实现边界的能力，会单独注明。
- 文中“任务”对应系统里的 `Monitor`；“运行记录”对应 `CollectTask` + `TaskEvent`。

## 1. 报告

### 模块定位

“报告”页是最新产出结果的发现页，面向“最近生成了什么”。它不是完整历史库，而是最近报告的轻量入口。

### 当前已实现功能

- 首页展示最近 10 份报告。
- 每张报告卡片展示标题、时间周期、报告类型、TL;DR、关联文章数、主题标签、所属任务。
- 支持点击进入单份报告详情页。
- 详情页支持两种展示模式：
  - 如果报告正文已生成结构化 Markdown，则展示完整文档、目录大纲、分节导航。
  - 如果正文不可用或无法解析，则回退为按文章分类展示关联文章列表。
- 详情页会展示报告日期、信息源数量、所属任务、事件摘要等元信息。

### 当前后端设计

- 数据主体是 `reports` 表。
- 核心字段包括：
  - `time_period`: `daily / weekly / custom`
  - `report_type`: `daily / weekly / research`
  - `content`: 渲染后的正文
  - `article_ids`: 关联文章 ID
  - `metadata`: 额外结构化信息，包含 `tldr`、`topics`、`events`、`monitor_id`、`monitor_name`、`global_tldr` 等
  - `published_to` / `publish_trace`: 记录输出渠道及发布轨迹
- API 已实现：
  - `GET /api/v1/reports`
  - `GET /api/v1/reports/{report_id}`
  - `DELETE /api/v1/reports/{report_id}`
  - `GET /api/v1/reports/filters`
- 自定义报告入口 `POST /api/v1/reports/custom` 仍返回 `501`，属于预留能力。

### 设计特点

- 报告是任务运行后的最终产物，不直接承担任务配置职责。
- 报告详情页优先消费结构化正文，其次回退到文章聚合视图，兼顾“最终产物阅读”和“生成失败时的可回看性”。
- `metadata.events` 已承载较丰富的事件级结构化信息，说明当前报告系统不只是纯 Markdown 存储，还兼顾机器可消费结果。

### 当前边界

- 首页仅展示最近 10 条，不承担复杂筛选。
- 自定义报告生成入口尚未实现。
- 报告编辑、重命名、重跑等能力当前没有单独入口。

## 2. 任务

### 模块定位

“任务”页是系统的核心编排入口。一个任务会把信息源、时间窗口、报告模板、AI 路由和输出配置组合成一条可重复执行的研究流水线。

### 当前已实现功能

- 列表查看全部任务。
- 创建任务与编辑任务。
- 配置任务基础字段：
  - 名称
  - 更新频率：`daily / weekly / custom`
  - 时间窗口 `window_hours`
  - 报告模板：`daily / weekly / research`
  - 自定义 cron 表达式
- 为任务选择多个信息源。
- 任务级信息源覆盖：
  - 通用抓取上限 `max_items`
  - arXiv 类源的 `keywords`、`max_results`
  - 社交源的用户名子集选择界面
- 配置 AI 路由：
  - `filter`
  - `keywords`
  - `global_summary`
  - `report`
- 为 `llm_openai` / `llm_codex` 填写任务级模型覆盖：
  - `model`
  - `timeout_sec`
  - `max_retry`
- 选择已启用的输出配置。
- 支持任务启停。
- 支持手动运行任务。
- 支持查看运行日志、运行摘要、事件流。
- 支持取消运行中的任务。
- 支持删除任务。

### 当前后端设计

- 数据主体是 `monitors` 表。
- 关键字段包括：
  - `source_ids`
  - `source_overrides`
  - `ai_routing`
  - `destination_ids`
  - `window_hours`
  - `custom_schedule`
  - `enabled`
- 运行态数据拆成两层：
  - `collect_tasks`: 记录一次 run 及其分 source 子任务
  - `task_events`: append-only 事件流，记录 collect/process/publish 阶段细节
- API 已实现：
  - `GET /api/v1/monitors`
  - `POST /api/v1/monitors`
  - `PATCH /api/v1/monitors/{monitor_id}`
  - `DELETE /api/v1/monitors/{monitor_id}`
  - `POST /api/v1/monitors/{monitor_id}/run`
  - `GET /api/v1/monitors/{monitor_id}/logs`
  - `GET /api/v1/monitors/{monitor_id}/runs`
  - `GET /api/v1/monitors/{monitor_id}/runs/{run_id}/events`
  - `POST /api/v1/monitors/{monitor_id}/runs/{run_id}/cancel`
  - `GET /api/v1/monitors/ai-routing/defaults`

### 调度与执行设计

- 调度器已实现“每日定时扫描所有启用任务并执行”。
- 周报定时任务函数仍是预留状态，未真正接入调度。
- 单次任务运行会：
  - 解析任务绑定的信息源
  - 计算实际时间窗口
  - 生成 run 级 `CollectTask`
  - 调用 orchestrator 执行采集、处理、报告生成、发布
  - 将结果写回 run 状态和阶段轨迹

### 设计特点

- 任务模块是“配置层 + 运行层”合一设计，用户不需要跳转到独立运行后台。
- 运行日志既保留 run 级摘要，也保留 event 级细节，适合定位是采集失败、处理失败还是发布失败。
- AI 路由是阶段化设计，不是全局单模型设计，这为后续成本/质量分层提供了空间。

### 当前边界

- `weekly` 调度仍是预留，并未真正自动运行。
- 前端已支持社交源用户名子集选择，但当前后端 `source_overrides` 归一化只稳定保留 `max_items / limit / max_results / keywords`，`usernames` 目前没有形成完整持久化与执行闭环。
- 后端注释里仍把部分更新/删除接口标成 “P1 预留”，但接口本身其实已经可用，属于“标注滞后于实现”。

## 3. 归档

### 模块定位

“归档”页是报告历史库，面向“过去所有生成结果的检索和回看”，与“报告”页共享同一份底层数据，但交互目标不同。

### 当前已实现功能

- 拉取最多 100 条历史报告。
- 按时间维度切换：
  - 总览
  - 日报
  - 周报
  - 自定义
- 按所属任务筛选。
- 删除历史报告。
- 点击任意报告卡片进入详情页。

### 当前后端设计

- 与“报告”模块共用 `reports` 表和 `/api/v1/reports` 接口。
- 归档页额外依赖 `GET /api/v1/reports/filters` 获取筛选维度聚合。
- 当前筛选维度包括：
  - `time_periods`
  - `report_types`
  - `categories`
  - `monitors`

### 设计特点

- “报告”与“归档”在产品上拆成两个视图，但数据模型上没有拆表，避免重复存储。
- 归档页目前以“轻筛选”方式组织历史数据，成本低，适合 MVP 阶段快速使用。

### 当前边界

- 当前前端只使用了“时间周期”和“所属任务”两个筛选条件，后端虽返回 `report_types` 和 `categories`，但前端暂未展开使用。
- 还没有全文检索、标签检索、分页翻页、批量操作。

## 4. 信息源

### 模块定位

“信息源”页负责维护全局输入池。任务并不直接定义抓取逻辑，而是从全局信息源池中选择和复用。

### 当前已实现功能

- 查看全部信息源。
- 按分类标签浏览：
  - blog
  - open_source
  - academic
  - social
- 展示每个信息源的状态、最近运行时间、品牌图标等。
- 新建信息源时根据 URL 和分类自动推断采集方式：
  - RSS
  - blog_scraper
  - github_trending
  - huggingface
- 点击信息源进入详情弹窗。
- 在详情弹窗中：
  - 编辑 RSS / blog_scraper / deepbrowse 的目标 URL
  - 编辑 `twitter_snaplytics` 的账号列表
  - 执行连接测试
  - 对 arXiv 类源执行带关键词、时间范围、最大结果数的测试

### 当前后端设计

- 数据主体是 `sources` 表。
- 核心字段包括：
  - `name`
  - `category`
  - `collect_method`
  - `config`
  - `enabled`
  - `last_collected`
- API 已实现：
  - `GET /api/v1/sources`
  - `GET /api/v1/sources/categories`
  - `GET /api/v1/sources/{source_id}`
  - `POST /api/v1/sources`
  - `PATCH /api/v1/sources/{source_id}`
  - `DELETE /api/v1/sources/{source_id}`
  - `POST /api/v1/sources/{source_id}/test`

### 设计特点

- 信息源采用“源定义”和“任务绑定”解耦设计，同一个 source 可以被多个任务复用。
- `config` 使用 JSON 承载不同采集器的特定参数，兼容 RSS、站点抓取、GitHub、Hugging Face、社交媒体等异构源。
- 测试接口不是简单 ping，而是实际调用采集器做一次 dry-run，能返回样例文章。

### 当前边界

- 新建信息源页面目前偏向“快速创建”，只暴露名称、分类、URL 三个入口字段；更复杂的 collector 参数仍依赖详情页修改或预置源同步。
- Source 状态当前主要根据最近一次 `CollectTask` 映射成 `healthy / running / error`，属于轻量健康度，不是完整监控系统。

## 5. 模型配置

### 模块定位

“模型配置”页负责维护全局 LLM provider 连接参数，是任务级 AI 路由的基础设施层。

### 当前已实现功能

- 展示当前支持的 provider 列表。
- 当前已内建两个 provider：
  - `llm_openai`
  - `llm_codex`
- 为每个 provider 配置：
  - `base_url`
  - `model`
  - `timeout_sec`
  - `max_retry`
  - `max_output_tokens`
  - `temperature`
  - `api_key`
- 支持启用/停用 provider。
- 支持在线连接测试。
- 保存配置后写入默认用户的 `settings.providers`。

### 当前后端设计

- provider 不是单独建表，而是作为“系统预置项 + 用户 settings 覆盖配置”存在。
- 预置项定义在 `PROVIDER_PRESETS` 中。
- 实际配置写入 `users.settings.providers`。
- API 已实现：
  - `GET /api/v1/providers`
  - `PATCH /api/v1/providers/{provider_id}`
  - `POST /api/v1/providers/{provider_id}/test`

### 设计特点

- provider 层只负责“怎么连接模型”，不负责“在哪个阶段使用模型”。
- 阶段选型放在任务模块，连接参数放在模型配置模块，两者分离。
- 测试接口会发起一次真实的最小化 JSON 请求，并统计延迟，便于快速校验连接是否通。

### 当前边界

- 当前只支持 2 个 LLM provider，没有多租户、多账号、多环境隔离。
- 没有 provider 优先级编排 UI，也没有默认 provider 管理页面；默认阶段路由仍由 routing profile 决定。
- API Key 当前随配置一起返回前端，说明这部分仍偏内部管理台设计，而非严格的密钥隔离方案。

## 6. 输出配置

### 模块定位

“输出配置”页负责定义报告落到哪里。任务产出报告后，会先写数据库，再根据任务选择的输出渠道继续发布。

### 当前已实现功能

- 展示当前支持的输出目标。
- 当前已内建 3 个目标：
  - `notion`
  - `obsidian`
  - `rss`
- 支持启用/停用输出目标。
- 支持为各目标维护独立配置：
  - Notion：`token`、`database_id`、`parent_page_id`、`title_property`、`summary_property`
  - Obsidian：`api_url`、`api_key`、`target_folder`
  - RSS：展示并复制 feed URL
- 在任务模块中选择已启用的输出配置进行绑定。

### 当前后端设计

- destination 同样不是单独建表，而是“预置项 + 用户 settings 覆盖配置”。
- 预置项定义在 `DESTINATION_PRESETS` 中。
- 实际配置写入 `users.settings.destinations`。
- API 已实现：
  - `GET /api/v1/destinations`
  - `PATCH /api/v1/destinations/{destination_id}`
  - `GET /api/v1/feed.xml`

### 发布链路设计

- orchestrator 在发布阶段会先解析实际 publish targets。
- 无论是否选择外部输出，`database` 都会被强制保留为首个目标，确保报告先落库。
- 若任务显式选择了 `destination_ids`，则会按“数据库 + 所选目标”发布。
- 发布结果会回写到报告的：
  - `published_to`
  - `publish_trace`
- 同时也会写入任务事件流，便于在任务日志中查看发布成功或失败。

### 各输出当前实现状态

- Notion：
  - 已有实际 sink 实现。
  - 支持将报告写入 database 或 parent page。
  - 支持标题字段和摘要字段映射。
- Obsidian：
  - 已有 sink 实现。
  - 当前后端真正消费的是 `vault_path`。
  - 前端填写的是 `target_folder`，后端会映射到 `vault_path` 使用。
- RSS：
  - 已有独立 feed endpoint。
  - 订阅内容来自数据库中最近的报告记录。

### 当前边界

- 输出配置页本身没有“测试连接”按钮，目前更偏保存配置而非完整联调页。
- Obsidian 前端字段命名是 REST API 风格，但后端 sink 当前主要按文件路径/`vault_path` 语义消费，存在命名抽象不完全一致的问题。
- 目标配置依赖默认用户 `settings`，还不是独立的可共享资源模型。

## 模块关系总结

当前系统可以理解为 3 层：

- 输入层：信息源
- 编排层：任务 + 模型配置
- 输出层：报告 / 归档 / 输出配置

典型流程如下：

1. 在“模型配置”里准备全局 LLM 连接参数。
2. 在“输出配置”里准备 Notion / Obsidian / RSS 目标。
3. 在“信息源”里维护全局 source 池并完成测试。
4. 在“任务”里把 source、AI 路由、时间窗口、输出目标组装成 Monitor。
5. 运行任务后生成 Report。
6. 在“报告”看最新结果，在“归档”看历史结果。

## 当前版本最重要的实现结论

- 系统主干已经打通：信息源 -> 任务 -> 报告 -> 输出。
- 任务模块是当前最完整的业务中枢，已经具备创建、编辑、手动运行、日志追踪、取消运行能力。
- 报告与归档共用同一底层报告模型，只是视图目标不同。
- 模型配置与输出配置当前都采用“预置项 + 用户 settings 覆盖”的轻量实现，而不是独立资源表。
- 仍有部分能力属于“界面已预埋 / 后端部分支持 / 尚未完全闭环”的状态，典型包括：
  - weekly 自动调度
  - 自定义报告生成
  - 任务级社交账号细粒度覆盖
  - 输出配置的显式连通性测试
