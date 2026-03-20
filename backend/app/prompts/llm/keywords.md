Extract structured fields for this AI news item and return strict JSON only.
Do not add explanations, markdown fences, or any non-JSON text.

The input may represent a clustered event bundle rather than a single article. When the content includes `Primary Source` and `Supporting Source` sections, synthesize one event-level result instead of repeating each source separately.

Rules:
- event_title: Chinese short title, recommended 12-32 chars, no ending punctuation, directly usable as event heading
- category: MUST be exactly one of ["要闻", "模型发布", "开发生态", "产品应用", "技术与洞察", "行业动态", "前瞻与传闻", "其他"]
- summary: one-sentence TL;DR in Chinese, <=60 characters. Get right to the core point.
- importance: "high" only for major industry events (flagship model release, major platform move, high-impact policy/regulation, or widely cited benchmark milestone); otherwise "normal"
- detail: normally 220-520 Chinese characters with factual completeness:
  1) what happened
  2) who发布/受影响
  3) technical/product changes
  4) key numbers/dates/constraints when available
  If the source only contains a short sentence plus a link and no additional facts, output a single grounded sentence instead of padding a long detail.
  If the input is a short social post but includes source metadata such as `Author`, platform hints, or distribution hints like `App Store`, prefer a 2-sentence brief instead of a bare one-liner:
  - sentence 1: `[发布方] 宣布 [产品] 已上线 [平台]` and mention download channel when grounded
  - sentence 2: clearly state which details remain unspecified in the source
  Format the detail using this structured Chinese editorial style:
  - You MUST write the detail in Chinese.
  - Start with a single impactful sentence summarizing the core takeaway, prefixed with "> " (blockquote format).
  - Follow with the narrative text. Use bullet points ("- ") if listing multiple features or metrics.
  - Bold ("**") key entity names, company names, or metrics for scannability.
  - Use backticks ("`") for technical terms or model names.
  - Do NOT copy raw markdown formatting (like badges or raw links / IDs) from the source.
  - Do NOT fabricate facts.
  - Do NOT pad the detail with repeated placeholder phrases such as "未知", "待定", "暂无信息", or "need more sources".

Additional required fields:
- who: publisher or affected party (Chinese entity name when possible)
- what: one-sentence core event description
- when: key date/time or rollout timeline
- metrics: list of concrete metrics (e.g. ["MMLU 92.3%", "价格 $$0.25/M tokens"]), [] if none
- availability: availability and constraints (region/access/pricing/rollout), empty string if no reliable information
- unknowns: key missing information in source, empty string if no reliable conclusion
- evidence: 1-3 critical supporting quotes/sentences from source in Chinese paraphrase

Example JSON output:
{
  "event_title": "...",
  "keywords": ["...", "..."],
  "summary": "...",
  "importance": "normal",
  "category": "模型发布",
  "detail": "> [一句话核心论点/主旨摘录]\n\n**[发布方]** 发布了 `[产品/模型名]`，带来了哪些**核心变化**。\n- 特性1：数据描述\n- 特性2：数据描述\n影响范围及未知的限制条件。",
  "who": "...",
  "what": "...",
  "when": "...",
  "metrics": ["..."],
  "availability": "...",
  "unknowns": "...",
  "evidence": "..."
}

Title: $title
Content: $content
