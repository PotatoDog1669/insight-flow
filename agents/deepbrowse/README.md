# deepbrowse — 自研浏览器 Agent

deepbrowse 是 LexDeepResearch 的核心差异化能力，作为信息获取的兜底方案和高级能力层。

## 定位

- **兜底采集**：对无 API / 无 RSS 的信息源，使用浏览器直接抓取
- **动态渲染**：处理 SPA 类技术博客需要 JS 渲染的场景
- **登录态管理**：通过 lexmount 管理的 Cookie/Token 注入浏览器上下文
- **API 挖掘**：通过浏览器 DevTools 分析隐藏 API 接口

## 架构

采用 Browser Provider 抽象层设计，支持本地 Playwright 和云端 CDP 两种模式。

相关实现与集成约束请优先参考 `docs/development/architecture.mdx` 与 `docs/plans/` 中的相关设计记录。

## 状态

该目录为独立模块/子仓库的占位目录，实际代码待集成。
