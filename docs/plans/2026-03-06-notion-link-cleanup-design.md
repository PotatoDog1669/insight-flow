# Notion Link Cleanup Design

**Goal:** 仅调整 Notion 落盘文本，移除 web 专用内部锚点，并把概览里的外链箭头替换为更适合 Notion 的文字链接。

## Scope

- 只影响 `backend/app/sinks/notion.py` 的 Notion 落盘内容规范化。
- 不修改 web 端渲染，不修改 report 原始 markdown 模板的通用输出。
- 保留可点击的外部原文链接，移除 `[#N](#event-N)` 这类仅在 web 页面有意义的内部跳转锚点。

## Behavior

- 在 Notion sink 规范化阶段，统一删除内部事件锚点：
  - `[#1](#event-1)`
  - `[#12](#event-12)`
- 在 Notion sink 规范化阶段，将 `[↗](https://...)` 替换为 `[原文](https://...)`。
- Notion 自动注入的 daily `概览` 区域改成显式文本链接：
  - 旧：`- [标题](url) [#1](#event-1)`
  - 新：`- 标题 [原文](url)`

## Rationale

- 内部锚点只在 web 页面中有跳转价值，落到 Notion 里会暴露 markdown 痕迹，影响观感。
- `↗` 在 Notion 里视觉噪音较大，`原文` 更直接，且更符合中文阅读场景。
- 把清洗逻辑集中在 Notion sink，可以保证：
  - web 端完全不受影响；
  - 模板已有内容和 sink 自动注入内容都能统一收口。

## Testing

- 更新 `backend/tests/sinks/test_notion_sink.py`：
  - 已有内容中的 `[#N](#event-N)` 会被移除；
  - 已有内容中的 `[↗](url)` 会改成 `[原文](url)`；
  - 自动注入的概览不再生成 `[#N](#event-N)`，而是输出 `标题 [原文](url)`。
