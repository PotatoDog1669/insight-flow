# Report Detail Page Alignment with Notion Export Template (Design)

**Date:** 2026-03-02  
**Status:** Approved (discussion)  
**Scope:** Frontend report detail page information architecture + visual/interaction behavior; no implementation in this document

---

## 1. Goal

将前端报告详情页对齐到当前“实际落盘到 Notion 的模板结构”，做到：

- 页面主体结构与 `report.content` 保持一致
- 在保持模板一致性的前提下提供可用交互（目录、折叠、锚点）
- 利用结构化字段（`events/topics/global_tldr`）做非侵入式增强

## 2. Source of Truth

### 2.1 Primary source

- `report.content`（Markdown 文本）是页面主结构唯一来源。
- 展示顺序、章节命名、段落顺序优先服从 `report.content`。

### 2.2 Enhancement sources

- `report.events`：事件级增强信息（来源、关键词、链接、发布时间）
- `report.global_tldr`：全局总结增强展示
- `report.topics`：右侧主题聚合

### 2.3 Fallback

当 `report.content` 缺失或为空时，回退至现有 `events/articles` 分组视图，不出现空白页。

## 3. Target Template Structure (Aligned with Notion export content)

页面需按以下层级呈现：

1. 报告标题：`# AI Daily Report — {date}`
2. 运行元信息：生成时间、输入/加工数量、stage/provider 信息
3. `## 全局总结与锐评`：总结 + 锐评
4. `## 正文`：
   - 内含报告标题与 `## 概览`
   - 按分类列事件清单（带序号与可点链接）
5. 事件详情区（逐条）：
   - `---`
   - `## {事件标题} #{index}`
   - `来源：一句话 TLDR`
   - 详情正文
   - 可选：关键词 / 关键指标 / 相关链接

## 4. Visual Direction

- 文档阅读优先（而非卡片流）：窄正文列、清晰标题层级、低对比边框。
- 保留当前系统主题变量（不引入新的设计体系）。
- 关键区块样式：
  - 全局总结：Callout 风格高亮
  - 运行元信息：低权重容器，默认收起
  - 事件正文：文档块风格 + 轻分隔

## 5. Interaction Design

### 5.1 Outline navigation

- 从 `report.content` 的标题自动提取目录（`#`/`##`）。
- 点击目录平滑跳转。
- 滚动联动高亮（scroll spy）。
- 支持 hash 深链接。

### 5.2 Collapsible sections

- 运行元信息默认收起。
- 事件详情 section 支持折叠/展开。
- 展开状态在当前会话保持（内存态即可）。

### 5.3 Event enhancement

- 对应事件标题行补充：来源数、发布时间。
- 关键词显示为轻量标签。
- 相关链接提供明确外链跳转行为。

### 5.4 Responsive behavior

- Desktop：左目录 + 中正文 + 右 Meta。
- Mobile：目录改抽屉；Meta 下沉到正文底部。
- Mobile 默认仅展开“全局总结 + 首个事件”。

## 6. Mapping Strategy (content <-> events)

- 通过事件标题中的 `#{index}` 或事件标题文本进行匹配。
- 优先使用 index 精确匹配，标题文本匹配作为兜底。
- 匹配失败时仅展示原始正文，不阻断渲染。

## 7. Error Handling & Degradation

- `report.content` 解析失败：降级为原文预格式化文本渲染。
- `events` 不可用：关闭事件增强，仅保留模板正文。
- 目录提取失败：不显示目录，不影响正文阅读。

## 8. Acceptance Criteria

- 页面主结构顺序与 `report.content` 一致。
- 目录可跳转并滚动高亮。
- 事件区支持折叠并在移动端可用。
- `events` 增强信息可正确附着到对应事件。
- `content` 缺失时存在稳定回退视图。
- 首屏阅读区无明显布局抖动。

## 9. Non-goals

- 不修改后端 Notion sink 的 block 写入策略。
- 不实现复杂富文本编辑能力。
- 不在本次改造中重写报告生成模板本身。
