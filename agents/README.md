# agents/ — 浏览器 Agent 模块

本目录存放 LexDeepResearch 可集成的各类浏览器 Agent 实现。

| 目录 | 说明 | 状态 |
|------|------|------|
| `deepbrowse/` | 自研浏览器 Agent，兜底采集 + 动态渲染 | 占位，待集成 |
| `browser-use/` | 社区方案 [browser-use](https://github.com/browser-use/browser-use) | 计划中 |
| `codex/` | Codex + Playwright 组合方案 | 计划中 |

后端通过 `backend/app/collectors/` 下的 Collector 插件按名称引用 Agent，与本目录的文件结构解耦。
