# Event Pipeline Fixtures

事件中心重构期间统一复用以下固定基线，不重复触发线上采集：

- `/Users/leo/workspace/Lexmount/LexDeepResearch/test_data/monitor_d57ca87c-d31d-4ca9-a5ad-2766215c4b3b/saved_report_7cab1763-b3ed-490f-8ef8-7de10a79a7f7`

约束：

- 所有 `candidate cluster / event extract / render / report` 调试优先基于这份导出目录回放
- 不将这份基线视为完整 `raw -> window` 采集快照，它只覆盖最新报告最终入报的 18 条文章
- 如需验证完整原始采集行为，应额外导出新的 `test_data` 基线包，而不是污染当前回归样本
